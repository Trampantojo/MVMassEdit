#!/usr/bin/python3
# BEER-WARE (Versión 42) - Creado por alguien, en alguna parte, en alguna fecha...
# Script para editar mensajes de forma masiva en MediaVida
# -----
# Para usarse se necesita obtener el hash de sesión del usuario.
# Esta cookie usa "HttpOnly" y para obtener el valor se tiene que abrir
# el panel de 'DevTools' del navegador pulsando CTRL+SHIFT+I e ir a la
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
import json
from requests.exceptions import ConnectionError
from typing import List, Tuple, Callable, Awaitable, Any
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


TEXT_SECONDS = {
    'segundos': 1,
    'minutos': 60,
    'horas': 3600
}

def css_xpath(tree: etree.ElementTree, css_selector: str) -> List[etree.Element]:
    """Helper function to get lxml elements using css selectors"""
    try:
        expression = HTMLTranslator().css_to_xpath(css_selector)
    except SelectorError:
        return []
    return tree.xpath(expression)

def get_post_url_values(url: str) -> Tuple[int, int, int]:
    """Helper function to get information of the post from the url
    Tuple result is: TID, NUM, PAG
    """
    g = re.search(r'(\d+)/(\d+)#(\d+)', url)
    if g is None:
        g = re.search(r'(\d+)#(\d+)', url)
        return (int(g[1]), int(g[2]), 1)
    return (int(g[1]), int(g[3]), int(g[2]))

class MVHttp(object):
    _protocol = 'https://'
    _domain = 'www.mediavida.com'

    def __init__(self, session_hash: str, max_tries: int = 3):
        self._max_tries = max_tries
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
        """Send a HTTP Get request"""
        r = self._requests.get(f"{self._protocol}{self._domain}/{url}", *args, **kwargs)
        if r.status_code == 200:
            return etree.parse(StringIO(r.text), self._htmlparser)
        return None

    def _post(self, url: str, *args: str, **kwargs: int) -> bool:
        """Send a HTTP Post request
        All is done successfully if the server redirect to the edited post
        """
        r = self._requests.post(f"{self._protocol}{self._domain}/{url}", *args, **kwargs)
        return r.status_code == 200 and '#' in r.url

    def _check_errors(self, tree: etree.ElementTree) -> bool:
        """
        MediaVida uses a rule to avoid requests flood. This method analyzes 
        the response to be compliant with this rule, this can block the 
        program execution for a long time.
        """
        error_elem = css_xpath(tree, "#errorbox li")
        if len(error_elem):
            g = re.search(r'Espera\s(\d+)\s(\w+)', error_elem[0].text)
            if g is not None:
                segs = int(g[1]) * TEXT_SECONDS[g[2]] + 1
                logging.info(f"Needs wait {segs} seconds to continue...")
                time.sleep(segs)
                return True
        return False

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

    async def edit_post(self, url: str, message: str, _try_count: int = 1) -> Tuple[str, bool]:
        """Try edit the given post."""
        
        async def try_again():
            """Try edit the page again"""
            if _try_count == self._max_tries:
                logging.error("Max-tries reached! can't edit the post.")
                return (url, False)  
            try_count_n = _try_count + 1
            logging.info(f"Trying to edit the post again ({try_count_n})...")
            return await self.edit_post(url, message, _try_count=try_count_n)

        logging.info(f"Editing '{url}'...")
        (tid, num, pag) = get_post_url_values(url)
        try:
            tree = self._get(f"foro/post.php?tid={tid}&num={num}&pagina={pag}")
            if not tree:
                return (url, False)
            current_message = css_xpath(tree, "#cuerpo")[0].text
            if current_message == message:
                logging.info("The post has already been edited. Omitting!")
                return (url, True)
            if self._check_errors(tree):
                return await try_again()
            token = css_xpath(tree, "#token")[0].get('value')
            fid = css_xpath(tree, "#fid")[0].get('value')
            if not self._post("foro/action/poster.php", data={
                'cuerpo': message,
                'token': token,
                'fid': fid,
                'tid': tid,
                'num': num,
                'pagina': pag
            }):
                return await try_again()
        except ConnectionError:
            logging.error("Failed! Can't edit the post")
            return await try_again()
        return (url, True)

class MultiRequestTask(object):
    def __init__(self, url: str, call_ref: Callable[..., Awaitable[Any]], call_args: List[Any]):
        self._url = url
        self._call_ref = call_ref
        self._call_args = call_args

    async def run(self) -> Callable[..., Awaitable[Any]]:
        return await self._call_ref(self._url, *self._call_args)

class AsyncMultiRequest(object):
    def __init__(self):
        self.reset()

    def jobs(self) -> int:
        return self._queue_out.qsize()

    def fails(self) -> List[str]:
        return self._fails

    def reset(self) -> None:
        self._fails = []
        self._queue_out = queue.SimpleQueue()

    def request_q(self, task: MultiRequestTask) -> None:
        self._queue_out.put(task)

    def process_queue(self, amount: int) -> None:
        loop = asyncio.get_event_loop()
        tasks = []
        for _ in range(amount):
            if not self._queue_out.empty():
                task = self._queue_out.get()
                tasks.append(task.run())
        (done, _) = loop.run_until_complete(asyncio.wait(tasks))
        for fut in done:
            (url, res) = fut.result()
            if not res:
                self._fails.append(url)

class MVMassEdit(object):
    def __init__(self, session_hash: str, max_tries: int):
        self._mvhttp = MVHttp(session_hash, max_tries)
        self._multi_edit = AsyncMultiRequest()

    def _process_fails(self) -> None:
        fails = self._multi_edit.fails()
        if any(fails):
            logging.warning(f"{len(fails)} posts can't be edited!")
            logging.debug(fails)
        with open('fails.json', 'w') as json_file:
            json.dump(fails, json_file)
    
    def _add_requests_q(self, posts: List[str], message: str, omit_first: bool) -> int:
        for url_post in posts:
            (_, _, num) = get_post_url_values(url_post)
            if num == 1 and omit_first:
                continue
            self._multi_edit.request_q(MultiRequestTask(url_post, self._mvhttp.edit_post, (message,)))
        return self._multi_edit.jobs()

    def prepare_from_file(self, filepath: str, message: str, omit_first: bool) -> bool:
        with open(filepath) as f:
            posts = json.load(f)
        if not any(posts):
            return False
        self._multi_edit.reset()
        jobs_count = self._add_requests_q(posts, message, omit_first)
        logging.info(f"Found {jobs_count} possible posts to edit...")
        return True

    def prepare(self, user: str, message: str, omit_first: bool) -> bool:
        posts = self._mvhttp.get_user_posts(user)
        if not any(posts):
            return False
        self._multi_edit.reset()
        posts.reverse() # Oldest first
        jobs_count = self._add_requests_q(posts, message, omit_first)
        logging.info(f"Found {jobs_count} possible posts to edit...")
        return True

    def run_loop(self, requests_amount: int, delay: int) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        while self._multi_edit.jobs():
            self._multi_edit.process_queue(requests_amount)
            time.sleep(delay)
        loop.close()
        self._process_fails()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='MediaVida Mass Edit Tool',
        add_help=True)
    parser.add_argument(
        '-u', '--user',
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
        '-ra', '--requests-amount',
        default=3,
        help='Multi-request amount')
    parser.add_argument(
        '-mt', '--max-tries',
        default=3,
        help="Amount of requests before abort the 'post' edition")
    parser.add_argument(
        '-f', '--file',
        help='Edit the messages declared in the file')
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

    mvmassedit = MVMassEdit(args.token, args.max_tries)
    if args.file:
        if not mvmassedit.prepare_from_file(args.file, args.message, args.omit_first):
            logging.error("Can't load any post from the file. Aborting!")
            exit(-1)
    else:
        if not args.user:
            logging.error('No user given. Aborting!')
            exit(-1)
        elif not mvmassedit.prepare(args.user, args.message, args.omit_first):
            logging.error("Can't load any post from the user. Aborting!")
            exit(-1)
    mvmassedit.run_loop(args.requests_amount, args.delay)
