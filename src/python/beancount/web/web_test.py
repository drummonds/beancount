import unittest
from os import path
import os
import re
import argparse

import urllib.request
import lxml.html

from beancount.web import web
from beancount.core import realization
from beancount.utils import test_utils


def scrape_urls(url_format, predicate, ignore_regexp=None):
    # The set of all URLs processed
    done = set()

    # The list of all URLs to process. We use a list here so we have
    # reproducible order if we repeat the test.
    process = ["/"]

    # Loop over all URLs remaining to process.
    while process:
        url = process.pop()

        # Mark as fetched.
        assert url not in done
        done.add(url)

        # Fetch the URL and check its return status.
        response = urllib.request.urlopen(url_format.format(url))
        predicate(response, url)

        # Skip served documents.
        if ignore_regexp and re.match(ignore_regexp, url):
            continue

        # Get all the links in the page and add all the ones we haven't yet
        # seen.
        for url in find_links(response.read()):
            if url in done or url in process:
                continue
            process.append(url)


def find_links(html_text):
    root = lxml.html.fromstring(html_text)
    for a in root.xpath('//a'):
        assert 'href' in a.attrib
        yield a.attrib['href']


def scrape(filename, predicate, port, quiet=True, extra_args=None):
    url_format = 'http://localhost:{}{{}}'.format(port)

    # Create a set of valid arguments to run the app.
    argparser = argparse.ArgumentParser()
    group = web.add_web_arguments(argparser)
    group.set_defaults(filename=filename,
                       port=port,
                       quiet=quiet)

    all_args = [filename]
    if extra_args:
        all_args.extend(extra_args)
    args = argparser.parse_args(args=all_args)

    thread = web.thread_server_start(args)

    # Skips:
    # - Docs cannot be read for external files.
    #
    # - Components views... well there are just too many, makes the tests
    #   impossibly slow. Just keep the A's so some are covered.
    scrape_urls(url_format, predicate, '^/(doc/|view/component/[^A])')

    web.thread_server_shutdown(thread)


class TestWeb(unittest.TestCase):

    def check_page_okay(self, response, url):
        self.assertEqual(200, response.status, url)

    @test_utils.docfile
    def test_scrape_empty_file(self, filename):
        """
        ;; A file with no entries in it.
        """
        scrape(filename, self.check_page_okay, test_utils.get_test_port())

    def test_scrape_basic(self):
        filename = path.join(test_utils.find_repository_root(__file__),
                             'examples', 'basic', 'basic.beancount')
        scrape(filename, self.check_page_okay, test_utils.get_test_port())

    def test_scrape_basic_view(self):
        filename = path.join(test_utils.find_repository_root(__file__),
                             'examples', 'basic', 'basic.beancount')
        scrape(filename, self.check_page_okay, test_utils.get_test_port(),
               extra_args=['--view', 'year/2013'])

    def test_scrape_starterkit(self):
        filename = path.join(test_utils.find_repository_root(__file__),
                             'examples', 'starterkit', 'starter.beancount')
        scrape(filename, self.check_page_okay, test_utils.get_test_port())

    def test_scrape_environ_var_ledger(self):
        try:
            filename = os.environ['TEST_LEDGER']
        except KeyError:
            raise unittest.SkipTest()
        if not path.exists(filename):
            raise unittest.SkipTest()
        scrape(filename, self.check_page_okay, test_utils.get_test_port())
