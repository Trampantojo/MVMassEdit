#!/usr/bin/python3
# BEER-WARE (Versión 42) - Creado por alguien, en alguna parte, en alguna fecha...
# Script para editar mensajes de forma masiva en MediaVida
# -----
# Para usarse se necesita obtener el hash de sesión del usuario.
# Esta cookie usa "HttpOnly" y para obtener el valor se tiene que abrir
# el panel de 'DevTools' pulsado CTRL+SHIFT+I e ir a la
# pestaña "Application" (Chrome) o "Storage" (Firefox), allí ir al
# apartado "Cookies" y copiar el valor de la cookie que se llama "sess".
# -----
import argparse
import requests
import re
import time
import queue
import asyncio
import sys
from requests.exceptions import ConnectionError
from typing import List, Tuple
from lxml import etree
from io import StringIO
from cssselect import HTMLTranslator, SelectorError
import logging
# Full verbosity
logging.basicConfig(level=logging.NOTSET,
    format='%(asctime)s %(levelname)s %(message)s',
    filename='mvmassedit.log',
    filemode='w')
logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))


def css_xpath(tree: etree.ElementTree, css_selector: str) -> List[etree.Element]:
    """Helper function to get lxml elements using css selectors"""
    try:
        expression = HTMLTranslator().css_to_xpath(css_selector)
    except SelectorError:
        return []
    return tree.xpath(expression)

def get_post_url_values(url: str) -> Tuple[int, int, int]:
    """Helper function to get information of the post from the url"""
    g = re.search(r'(\d+)/(\d+)#(\d+)', url)
    if g is None:
        g = re.search(r'(\d+)#(\d+)', url)
        (tid, num, pag) = (g[1], g[2], 1)
    else:
        (tid, num, pag) = (g[1], g[3], g[2])
    return (tid, num, pag)

class MVHttp(object):
    _protocol = 'https://'
    _domain = 'www.mediavida.com'

    def __init__(self, session_hash: str):
        self._requests = requests.Session()
        self._htmlparser = etree.HTMLParser()
        session_cookie = {
            "version": 0,
            "name": 'sess',
            "value": session_hash,
            "port": None,
            "domain": self._domain,
            "path": '/',
            "secure": True,
            "expires": None,
            "discard": True,
            "comment": None,
            "comment_url": None,
            "rest": {},
            "rfc2109": False
        }
        self._requests.cookies.set(**session_cookie)

    def _get(self, url: str, *args: str, **kwargs: int) -> etree.ElementTree:
        r = self._requests.get(f"{self._protocol}{self._domain}/{url}", *args, **kwargs)
        if r.status_code == 200:
            return etree.parse(StringIO(r.text), self._htmlparser)
        return None

    def _post(self, url: str, *args: str, **kwargs: int) -> bool:
        kwargs['allow_redirects'] = False
        r = self._requests.post(f"{self._protocol}{self._domain}/{url}", *args, **kwargs)
        return r.status_code == 200

    def _check_errors(self, tree: etree.ElementTree) -> None:
        error_elem = css_xpath(tree, "#errorbox li")
        if len(error_elem):
            g = re.search(r'Espera\s(\d+)\s(\w+)', error_elem[0].text)
            seconds_map = {
                'segundos': 1,
                'minutos': 60,
                'horas': 3600
            }
            if g is not None:
                segs = int(g[1]) * seconds_map[g[2]] + 1
                logging.info(f"Needs wait {segs} seconds to continue...")
                time.sleep(segs)

    def get_user_posts(self, user: str) -> List[str]:
        """Gets all the user posts meta-data"""
        tree = self._get(f"id/{user}/posts")
        if not tree:
            return []
        last_page_elem = css_xpath(tree, "ul.pg > li:last-child a")[0]
        last_page_num = int(last_page_elem.text)
        posts = []
        for i in range(1, last_page_num + 1):
            tree = self._get(f"id/{user}/posts/{i}")
            links = css_xpath(
                tree,
                "#tablatemas td:nth-child(2) div.thread > a[href^='/foro/']")
            posts += [link.get('href') for link in links]
        return posts

    async def edit_post(self, url: str, message: str) -> Tuple[str, bool]:
        """
        Try edit the given post. 
        MediaVida uses a rule to avoid requests flood. This method analyzes 
        the response to be compliant with this rule, this can block the 
        program execution for a long time.
        """
        logging.info(f"Editing '{url}'...")
        (tid, num, pag) = get_post_url_values(url)
        try:
            tree = self._get(f"foro/post.php?tid={tid}&num={num}&pagina={pag}")
            if not tree:
                return False
            current_message = css_xpath(tree, "#cuerpo")[0].text
            if current_message == message:
                logging.info("The post is already edited. Omitting.")
                return (url, True)
            self._check_errors(tree)
            token = css_xpath(tree, "#token")[0].get('value')
            fid = css_xpath(tree, "#fid")[0].get('value')
            return (url, self._post("foro/action/poster.php", data={
                'cuerpo': message,
                'token': token,
                'fid': fid,
                'tid': tid,
                'num': num,
                'pagina': pag
            }))
        except ConnectionError:
            logging.error("Failed! Can't edit the post")
            return (url, False)

class MultiEditRequest(object):
    def __init__(self, mvhttp: MVHttp):
        self._mvhttp = mvhttp
        self.reset()

    def jobs(self) -> int:
        return self._queue_out.qsize()

    def fails(self) -> List[str]:
        return self._fails

    def reset(self) -> None:
        self._fails = []
        self._queue_out = queue.SimpleQueue()

    def request_q(self, url: str, message: str) -> None:
        self._queue_out.put((url, message))

    def process_queue(self, amount: int) -> None:
        loop = asyncio.get_event_loop()
        tasks = []
        for _ in range(amount):
            if not self._queue_out.empty():
                (url, message) = self._queue_out.get()
                tasks.append(self._mvhttp.edit_post(url, message))
        (done, _) = loop.run_until_complete(asyncio.wait(tasks))
        # TODO: Add support to max-tries
        for fut in done:
            (url, res) = fut.result()
            if not res:
                self._fails.append(url)

class MVMassEdit(object):
    # FIXME: Improve to use multi-requests.
    # MV uses a window time anti-flood feature.
    _max_requests = 1

    def __init__(self, session_hash: str, omit_first: bool):
        self._omit_first = omit_first
        self._mvhttp = MVHttp(session_hash)
        self._multi_edit = MultiEditRequest(self._mvhttp)

    def prepare(self, user: str, message: str) -> None:
        posts = self._mvhttp.get_user_posts(user)
        logging.info(f"Found {len(posts)} possible posts to edit...")
        self._multi_edit.reset()
        posts.reverse()
        for url_post in posts:
            (_, _, num) = get_post_url_values(url_post)
            if num == 1 and self._omit_first:
                continue
            self._multi_edit.request_q(url_post, message)

    def run_loop(self, delay: int) -> None:
        fails = []
        loop = asyncio.get_event_loop()
        while self._multi_edit.jobs():
            self._multi_edit.process_queue(self._max_requests)
            time.sleep(delay)
        loop.close()
        fails = self._multi_edit.fails()
        if any(fails):
            logging.warning(f"{len(fails)} posts can't be edited!")
            logging.debug(fails)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='MediaVida Mass Edit Tool',
        add_help=True)
    parser.add_argument(
        '-u', '--user',
        required=True,
        help='User login')
    parser.add_argument(
        '-t', '--token',
        help='User session token')
    parser.add_argument(
        '-m', '--message',
        default=".",
        help='New message')
    parser.add_argument(
        '-d', '--delay',
        default=2,
        help='Multi-request delay')
    parser.add_argument(
        '--omit-first',
        action='store_true',
        help='Omit the first post of the thread')
    args = parser.parse_args()
    if args.token is None:
        args.token = input(f"MV '{args.user}' session hash: ")
    if not args.token:
        logging.error('No session token given. Aborting!')
        exit(-1)

    mvmassedit = MVMassEdit(args.token, args.omit_first)
    mvmassedit.prepare(args.user, args.message)
    mvmassedit.run_loop(args.delay)
