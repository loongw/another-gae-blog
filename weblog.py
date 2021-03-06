'''
Entry of WEBlog

Created on 2012-10-26

@author: DANG Zhengfa
'''
# load system modules
import webapp2
from webapp2 import RequestHandler
from google.appengine.ext.webapp.util import run_wsgi_app
from webapp2 import uri_for, Route
# from webapp2_extras.routes import RedirectRoute
import logging
import sys
# from webapp2_extras import i18n

# load modules defined by this app
from model import Entry, Category, Link, Comment
from utilities import render_template, dump
from captcha import submit, displayhtml, RecaptchaResponse
from config import Configuration
from BaseRequestHandler import BaseRequestHandler


# generate link pairs for navlist
def generateNavList(total_posts, current_page, posts_per_page):
    navlist = []
    if total_posts > posts_per_page:
        # we need more than one pages
        total_pages = total_posts / posts_per_page
        if (total_posts % posts_per_page) != 0:
            total_pages += 1
        logging.info("total pages = %d" % (total_pages))
        # generate links
        for page_number in range(1, total_pages + 1):
            if page_number != current_page:
                navlist.append((page_number, "%d" % (page_number)))

        if current_page > 1:
            navlist.insert(0, (current_page - 1, "Prev"))
        if current_page < total_pages:
            navlist.append((current_page + 1, "Next"))
    return navlist


class IndexHandler(BaseRequestHandler):
    '''
    classdocs
    '''
    def get(self, page="1", cate_slug=""):
        t_values = {}
        page = int(page)
        logging.info("IndexHandler - get: page = %d, cate_slug = %s" % (page, cate_slug))

        # find all entries by order
        query = Entry.all().filter("is_external_page =", True).filter("entrytype =", 'post').order("-date")
        # add category filter?
        if cate_slug:
            cates = Category.all().filter("slug =", cate_slug)
            if cates:
                query = query.filter("category =", cates[0])

        # pagination
        total_posts = query.count()
        q_limit = Configuration["posts_per_page"]
        q_offset = (page - 1) * Configuration["posts_per_page"]
        logging.info("limit = %d, offset = %d" % (q_limit, q_offset))

        # get entries
        entries = query.fetch(limit=q_limit, offset=q_offset)
        t_values['entries'] = entries

        # show entries for debug purpose
        # for entry in entries:
        #     logging.info("entry title: %s, public = %s, cate = %s" % (entry.title, entry.is_external_page, entry.category.name))

        logging.info("total posts = %d, current_page = %d, posts_per_page = %d" % (total_posts, page, Configuration['posts_per_page']))
        t_values['navlist'] = generateNavList(total_posts, page, Configuration["posts_per_page"])
        # logging.info(t_values['navlist'])

        # find all links
        links = Link.all().order("date")
        t_values['links'] = links

        # find all categories
        categories = Category.all()
        t_values['categories'] = categories

        # find all pages
        pages = Entry.all().filter("is_external_page =", True).filter("entrytype =", 'page').order("date")
        t_values['pages'] = pages

        # show index page
        return self.response.out.write(render_template("index.html", t_values, "basic", False))

    def post(self):
        pass


class PostHandler(BaseRequestHandler):
    '''
    classdocs
    '''
    def get(self, post_slug=""):
        if post_slug:
            t_values = {}

            posts = Entry.all().filter("slug =", post_slug)
            if posts.count() == 1:
                logging.warning("find one post with slug=%s" % (post_slug))
                posts = posts.fetch(limit=1)
                post = posts[0]
                t_values['post'] = post
                # dump(post)

                # find all comments
                comments = Comment.all().filter("entry =", post).order("date")
                t_values['comments'] = comments
            else:
                logging.warning("%d entries share the same slug %s" % (posts.count(), post_slug))

            links = Link.all().order("date")
            t_values['links'] = links

            categories = Category.all()
            t_values['categories'] = categories

            pages = Entry.all().filter("is_external_page =", True).filter("entrytype =", 'page').order("date")
            t_values['pages'] = pages

            return self.response.out.write(render_template("post.html", t_values, "basic", False))
        else:
            self.redirect(uri_for("weblog.index"))

    def post(self, post_slug=""):
        if post_slug:
            t_values = {}

            post_id = self.request.POST['post_id']
            post = Entry.get_by_id(long(post_id))
            if post:
                # ok, we find the post, try to add comment to this post
                logging.warning("find one post with post_id %s" % (post_id))
                t_values['post'] = post
                # dump(post)

                # check google recaptcha, these two fileds might not exist due to connection to reCAPTCHA
                recaptcha_challenge_field = self.request.POST.get('recaptcha_challenge_field', "")
                recaptcha_response_field = self.request.POST.get('recaptcha_response_field', "")
                remote_ip = self.request.environ['REMOTE_ADDR']
                private_key = "6LdwFdISAAAAAOYRK7ls3O-kXPTnYDEstrLM2MRo"
                antispam_flag = False
                try:
                    result = submit(recaptcha_challenge_field, recaptcha_response_field, private_key, remote_ip)
                    logging.info("google recaptcha %s, %s" % (result.is_valid, result.error_code))
                    if result.is_valid:
                        antispam_flag = True
                except:
                    e = sys.exc_info()[0]
                    logging.info(e)

                # create comment for this post
                if antispam_flag:
                    logging.info("PostManager - add comment")
                    comm_author = self.request.POST['author']
                    comm_email = self.request.POST['email']
                    comm_weburl = self.request.POST['weburl']
                    comm_content = self.request.POST['comment']
                    comment_ip = self.request.environ['REMOTE_ADDR']
                    comm = Comment(entry=post, author=comm_author, email=comm_email, weburl=comm_weburl, content=comm_content, ip=comment_ip)
                    comm.put()
                    t_values['alert_message'] = "Thanks %s for your comment!" % (comm_author)
                else:
                    logging.warning("comment ignored because antispam failed")
                    t_values['alert_message'] = "Sorry, your comment was ignored because of reCAPTCHA failure!"

                # find all comments
                comments = Comment.all().filter("entry =", post).order("date")
                logging.info("PostHandler, post, find %d comments" % (comments.count()))
                if post_id:
                    # only update commentcount when new comment is added
                    post.commentcount = comments.count()
                    post.put()
                t_values['comments'] = comments
            else:
                logging.warning("post_id %s does not exist" % (post_id))

            links = Link.all().order("date")
            t_values['links'] = links

            categories = Category.all()
            t_values['categories'] = categories
    
            pages = Entry.all().filter("is_external_page =", True).filter("entrytype =", 'page').order("date")
            t_values['pages'] = pages

            return self.response.out.write(render_template("post.html", t_values, "basic", False))
        else:
            self.redirect(uri_for("weblog.index"))


class PageHandler(BaseRequestHandler):
    def get(self, page_slug=""):
        if page_slug:
            t_values = {}

            posts = Entry.all().filter("is_external_page =", True).filter("entrytype =", 'page').filter("slug =", page_slug)
            if posts.count() == 1:
                logging.warning("find one page with slug=%s" % (page_slug))
                posts = posts.fetch(limit=1)
                post = posts[0]
                t_values['post'] = post
                # dump(post)

                # find all comments
                comments = Comment.all().filter("entry =", post).order("date")
                t_values['comments'] = comments
            else:
                logging.warning("%d entries share the same slug %s" % (posts.count(), page_slug))

            links = Link.all().order("date")
            t_values['links'] = links

            categories = Category.all()
            t_values['categories'] = categories

            pages = Entry.all().filter("is_external_page =", True).filter("entrytype =", 'page').order("date")
            t_values['pages'] = pages

            return self.response.out.write(render_template("page.html", t_values, "basic", False))
        else:
            self.redirect(uri_for("weblog.index"))

    def post(self, post_slug=""):
        pass


class LocaleHandler(RequestHandler):
    '''
    classdocs
    '''
    def get(self):
        referer = self.request.referer
        locale = self.request.GET.get("value", "en_US")
        logging.info("LocaleHandler: %s set locale to %s" % (referer, locale))
        if locale:
            self.response.set_cookie("locale", locale)
        if referer:
            self.redirect(referer)
        else:
            self.redirect(uri_for("weblog.index"))


class InitBlog(BaseRequestHandler):
    '''
    classdocs
    '''
    def get(self):
        link = Link(title="linkx1", target="http://baidu.com", sequence=9)
        link.put()

        link = Link(title="linkx2", target="http://baidu.com", sequence=9)
        link.put()

        link = Link(title="linkx3", target="http://baidu.com", sequence=9)
        link.put()
        return self.response.out.write(render_template("index.html", {}, "basic", False))

##########################################################
# define routers
routes = [
          Route('/', handler='weblog.IndexHandler', name="weblog.index"),
          Route('/<page:\d+>', handler='weblog.IndexHandler', name="weblog.index.page"),
          Route('/cate/<cate_slug>', handler='weblog.IndexHandler', name="weblog.index.cate"),

          Route('/page/<page_slug>', handler='weblog.PageHandler', name="weblog.page"),
          Route('/post/<post_slug>', handler='weblog.PostHandler', name="weblog.post"),
          Route('/init', handler='weblog.InitBlog', name="init"),
          Route('/locale', handler='weblog.LocaleHandler', name="weblog.locale"),
          ]

application = webapp2.WSGIApplication(routes, debug=True)


# main goes here
def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
