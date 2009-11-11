from tg import expose, validate, require, request, response, config
from pylons import tmpl_context, templating
from sqlalchemy.orm import undefer

from simpleplex.lib import helpers
from simpleplex.lib.helpers import expose_xhr, paginate, redirect, url_for
from simpleplex.lib.base import RoutingController
from simpleplex.model import DBSession, fetch_row, Podcast, Media, Topic


class PodcastsController(RoutingController):
    """Podcast actions -- episodes are handled in the MediaController"""

    def __init__(self, *args, **kwargs):
        """Populate the :obj:`pylons.tmpl_context`` with topics.

        Used by :data:`simpleplex.templates.helpers` to render the
        topic index flyout slider.

        """
        super(PodcastsController, self).__init__(*args, **kwargs)
        tmpl_context.topics = DBSession.query(Topic)\
            .options(undefer('published_media_count'))\
            .filter(Topic.published_media_count >= 1)\
            .order_by(Topic.name)\
            .all()


    @expose('simpleplex.templates.podcasts.index')
    @paginate('episodes', items_per_page=12, items_first_page=7)
    def index(self, page=1, **kwargs):
        """List podcasts and podcast media.

        Our custom paginate decorator allows us to have fewer podcast episodes
        display on the first page than on the rest with the ``items_first_page``
        param. See :class:`simpleplex.lib.custompaginate.CustomPage`.

        :param page: Page number, defaults to 1.
        :type page: int
        :rtype: dict
        :returns:
            podcasts
                The :class:`~simpleplex.model.podcasts.Podcast` instance
            episodes
                The list of :class:`~simpleplex.model.media.Media` instances
                for this page.

        """
        episodes = DBSession.query(Media)\
            .filter(Media.podcast_id != None)\
            .order_by(Media.publish_on.desc())\
            .options(undefer('comment_count_published'))
        episodes = self._filter(episodes)

        podcasts = DBSession.query(Podcast)\
            .options(undefer('published_media_count'))\
            .all()

        return dict(
            podcasts = podcasts,
            episodes = episodes,
        )


    @expose('simpleplex.templates.podcasts.view')
    @paginate('episodes', items_per_page=10)
    def view(self, slug, page=1, **kwargs):
        """View a podcast and the media that belongs to it.

        :param slug: A :attr:`~simpleplex.model.podcasts.Podcast.slug`
        :param page: Page number, defaults to 1.
        :type page: int
        :rtype: dict
        :returns:
            podcast
                A :class:`~simpleplex.model.podcasts.Podcast` instance.
            episodes
                A list of :class:`~simpleplex.model.media.Media` instances
                that belong to the ``podcast``.
            podcasts
                A list of all the other podcasts

        """
        podcast = fetch_row(Podcast, slug=slug)
        episodes = self._filter(podcast.media)\
            .order_by(Media.publish_on.desc())

        podcasts = DBSession.query(Podcast)\
            .options(undefer('published_media_count'))\
            .all()

        return dict(
            podcast = podcast,
            episodes = episodes,
            podcasts = podcasts,
        )


    @expose()
    def feed(self, slug, **kwargs):
        """Serve the feed as RSS 2.0.

        If :attr:`~simpleplex.model.podcasts.Podcast.feedburner_url` is
        specified for this podcast, we redirect there.

        :param slug: A :attr:`~simpleplex.model.podcasts.Podcast.slug`
        :param page: Page number, defaults to 1.
        :type page: int
        :rtype: dict
        :returns:
            podcast
                A :class:`~simpleplex.model.podcasts.Podcast` instance.
            episodes
                A list of :class:`~simpleplex.model.media.Media` instances
                that belong to the ``podcast``.
            podcasts
                A list of all the other podcasts

        """
        podcast = fetch_row(Podcast, slug=slug)
        episodes = self._filter(podcast.media)\
            .order_by(Media.publish_on.desc())

        podcasts = DBSession.query(Podcast)\
            .options(undefer('published_media_count'))\
            .all()

        return dict(
            podcast = podcast,
            episodes = episodes,
            podcasts = podcasts,
        )


    @expose()
    def feed(self, slug, **kwargs):
        """Serve the feed as RSS 2.0.

        If :attr:`~simpleplex.model.podcasts.Podcast.feedburner_url` is
        specified for this podcast, we redirect there if the useragent
        does not contain 'feedburner', as described here:
        http://www.google.com/support/feedburner/bin/answer.py?hl=en&answer=78464

        :param feedburner_bypass: If true, the redirect to feedburner is disabled.
        :rtype: Dict
        :returns:
            podcast
                A :class:`~simpleplex.model.podcasts.Podcast` instance.
            episodes
                A list of :class:`~simpleplex.model.media.Media` instances
                that belong to the ``podcast``.

        Renders: :data:`simpleplex.templates.podcasts.feed` XML

        """
        podcast = fetch_row(Podcast, slug=slug)

        if (podcast.feedburner_url
            and not 'feedburner' in request.environ['HTTP_USER_AGENT'].lower()
            and not kwargs.get('feedburner_bypass', False)):
            redirect(podcast.feedburner_url.encode('utf-8'))

        episodes = self._filter(podcast.media)\
            .order_by(Media.publish_on.desc())[:25]

        template_vars = dict(
            podcast = podcast,
            episodes = episodes,
        )

        for type in ('application/rss+xml', 'application/xml'):
            if type in request.environ['HTTP_ACCEPT']:
                response.content_type = type
        else:
            response.content_type = 'text/html'

        # Manually render XML from genshi since tg.render.render_genshi is too stupid to support it.
        template_name = config['pylons.app_globals'].dotted_filename_finder.get_dotted_filename(
            'simpleplex.templates.podcasts.feed', template_extension='.xml')
        return templating.render_genshi(template_name, extra_vars=template_vars, method='xml')


    def _filter(self, query):
        """Filter a query for only published, undeleted media."""
        return query\
            .filter(Media.status >= 'publish')\
            .filter(Media.status.excludes('trash'))