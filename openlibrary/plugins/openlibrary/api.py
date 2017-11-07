"""
This file should be for internal APIs which Open Library requires for
its experience. This does not include public facing APIs with LTS
(long term support)
"""

import web
import simplejson

from infogami.utils import delegate
from infogami.utils.view import render_template
from openlibrary import accounts
from openlibrary.plugins.worksearch.subjects import get_subject
from openlibrary.core import ia, db, models, lending, cache, helpers as h


ONE_HOUR = 60 * 60
BOOKS_PER_CAROUSEL = 6

class featured_subjects(delegate.page):
    path = "/home/subjects"

    def GET(self):
        return delegate.RawText(simplejson.dumps(get_featured_subjects()),
                                content_type="application/json")

def get_featured_subjects():
    # this function is memozied with background=True option.
    # web.ctx must be initialized as it won't be avaiable to the background thread.
    if 'env' not in web.ctx:
        delegate.fakeload()

    subjects = {}
    FEATURED_SUBJECTS = [
        'art', 'science_fiction', 'fantasy', 'biographies', 'recipes',
        'romance', 'textbooks', 'children', 'history', 'medicine', 'religion',
        'mystery_and_detective_stories', 'plays', 'music', 'science'
    ]
    for subject in FEATURED_SUBJECTS:
        subjects[subject] = get_subject('/subjects/' + subject, sort='edition_count')
    return subjects

# cache the results in memcache for 1 hour
get_featured_subjects = cache.memcache_memoize(
    get_featured_subjects, "get_featured_subjects", timeout=ONE_HOUR)

class book_availability(delegate.page):
    path = "/availability/v2"

    def GET(self):
        i = web.input(type='', ids='')
        id_type = i.type
        ids = i.ids.split(',')
        result = self.get_book_availability(id_type, ids)
        return delegate.RawText(simplejson.dumps(result),
                                content_type="application/json")

    def POST(self):
        i = web.input(type='')
        j = simplejson.loads(web.data())
        id_type = i.type
        ids = j.get('ids', [])
        result = self.get_book_availability(id_type, ids)
        return delegate.RawText(simplejson.dumps(result),
                                content_type="application/json")

    def get_book_availability(self, id_type, ids):
        return (
            lending.get_availability_of_works(ids) if id_type == "openlibrary_work"
            else
            lending.get_availability_of_editions(ids) if id_type == "openlibrary_edition"
            else
            lending.get_availability_of_ocaids(ids) if id_type == "identifier"
            else []
        )

class work_likes(delegate.page):
    path = "/works/OL(\d+)W/likes"
    encoding = "json"

    def GET(self, work_id):
        user = accounts.get_current_user()
        username = user.key.split('/')[2] if user else None
        work_likes = models.Likes.count(work_id=work_id, username=username)
        result = {
            'work_id': int(work_id),
            'work_likes_count': work_likes['work_likes_count']
        }
        if username and 'user_likes_work' in work_likes:
            result['user_likes_work'] = work_likes.user_likes_work
        return delegate.RawText(simplejson.dumps(result), content_type="application/json")

    def POST(self, work_id):
        user = accounts.get_current_user()
        i = web.input(edition_id=None, action=None)
        if not user:
            key = i.edition_id if i.edition_id else ('/works/OL%sW' % work_id) 
            raise web.seeother('/account/login?redirect=%s' % key)

        if i.action not in ['like', 'unlike']:
            return delegate.RawText(simplejson.dumps({
                'error': 'Invalid action: must be "like" or "unlike"'
            }), content_type="application/json")

        username = user.key.split('/')[2]
        like = (i.action == 'like')
        edition_id = int(i.edition_id.split('/')[2][2:-1]) if i.edition_id else None
        work_likes = models.Likes.register(
            username=username, work_id=work_id, edition_id=edition_id,
            like=like)
        return delegate.RawText(simplejson.dumps({
            'work_id': int(work_id),
            'work_like_count': work_likes['work_like_count'],
            'user_likes_work': work_likes['user_likes_work']
        }), content_type="application/json")
        

class work_editions(delegate.page):
    path = "(/works/OL\d+W)/editions"
    encoding = "json"

    def GET(self, key):
        doc = web.ctx.site.get(key)
        if not doc or doc.type.key != "/type/work":
            raise web.notfound('')
        else:
            i = web.input(limit=50, offset=0)
            limit = h.safeint(i.limit) or 50
            offset = h.safeint(i.offset) or 0

            data = self.get_editions_data(doc, limit=limit, offset=offset)
            return delegate.RawText(simplejson.dumps(data), content_type="application/json")

    def get_editions_data(self, work, limit, offset):
        if limit > 1000:
            limit = 1000

        keys = web.ctx.site.things({"type": "/type/edition", "works": work.key, "limit": limit, "offset": offset})
        editions = web.ctx.site.get_many(keys, raw=True)

        size = work.edition_count
        links = {
            "self": web.ctx.fullpath,
            "work": work.key,
        }

        if offset > 0:
            links['prev'] = web.changequery(offset=min(0, offset-limit))

        if offset + len(editions) < size:
            links['next'] = web.changequery(offset=offset+limit)

        return {
            "links": links,
            "size": size,
            "entries": editions
        }

class author_works(delegate.page):
    path = "(/authors/OL\d+A)/works"
    encoding = "json"

    def GET(self, key):
        doc = web.ctx.site.get(key)
        if not doc or doc.type.key != "/type/author":
            raise web.notfound('')
        else:
            i = web.input(limit=50, offset=0)
            limit = h.safeint(i.limit) or 50
            offset = h.safeint(i.offset) or 0

            data = self.get_works_data(doc, limit=limit, offset=offset)
            return delegate.RawText(simplejson.dumps(data), content_type="application/json")

    def get_works_data(self, author, limit, offset):
        if limit > 1000:
            limit = 1000

        keys = web.ctx.site.things({"type": "/type/work", "authors": {"author": {"key": author.key}}, "limit": limit, "offset": offset})
        works = web.ctx.site.get_many(keys, raw=True)

        size = author.get_work_count()
        links = {
            "self": web.ctx.fullpath,
            "author": author.key,
        }

        if offset > 0:
            links['prev'] = web.changequery(offset=min(0, offset-limit))

        if offset + len(works) < size:
            links['next'] = web.changequery(offset=offset+limit)

        return {
            "links": links,
            "size": size,
            "entries": works
        }
