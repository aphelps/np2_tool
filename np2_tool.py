#!/usr/bin/env python3

import argparse
import json
import math
import os
import pickle
import requests
import sys

################################################################################
# Constants
#

# 3 hours per LY
LIGHT_YEAR_TIME = 3

# 1 star scale = 8 light years observed
# docs say 1/16, but seem to be wrong
LIGHT_YEAR_SCALE = 8


def handle_args():
    global game_id

    parser = argparse.ArgumentParser()

    parser.add_argument("-l", "--login", help="Login ID")
    parser.add_argument("-p", "--password", help="password")
    parser.add_argument("-C", "--credentials", default="creds.np", help="Cookies output file [default: %(default)s]")
    parser.add_argument("-g", "--gameid", type=int, default=5380395345117184, help="Game ID")

    parser.add_argument("-v", "--verbose", action="store_true")

    parser.add_argument("-E", "--upgrade_economy", action="store_true")
    parser.add_argument("-I", "--upgrade_industry", action="store_true")
    parser.add_argument("-S", "--upgrade_science", action="store_true")
    parser.add_argument("--execute", action="store_true")

    options = parser.parse_args()

    if (not os.path.isfile(options.credentials)) and (options.login is None or options.password is None):
        print("Must provide cookes file or login/password")
        sys.exit(1)

    game_id = options.gameid

    return options


def load_cookies(login, password, credentials):
    global cookies

    cookies = None
    if login:
        print("Logging in with email/password")
        cookies = requests.post('https://np.ironhelmet.com/arequest/login',
                                data={'type': 'login',
                                      'alias': login,
                                      'password': password}).cookies
        # print("Cookies: %s" % cookies)

        if credentials:
            with open(credentials, "wb") as creds:
                pickle.dump(cookies, creds)
                print("Wrote cookies to %s" % credentials)
    else:
        # Read the cookies from a file
        with open(credentials, 'rb') as creds:
            cookies = pickle.load(creds)
            print("Read cookies from %s" % credentials)

    return cookies


def get_universe():
    global universe

    response = requests.post('https://np.ironhelmet.com/trequest/order',
                             data={'type':'order',
                                   'order':'full_universe_report',
                                   'version':'',
                                   'game_number':game_id},
                             cookies=cookies)
    # print("Universe: %s" % json.dumps(universe))

    universe = response.json()
    if response.status_code != requests.codes.ok:
        print("get_universe(): request failed, code %d" % response.status_code)
        print("  data: %s" % response.text)
        sys.exit(1)

    if 'player_uid' not in universe['report']:
        print("get_universe(): invalid universe: %s" % (json.dumps(universe)))
        sys.exit()

    with open("universe.json", "w") as f:
        f.write(json.dumps(universe))
    return universe



# Star format:
#     {
#         u'e': 4,             # Economy
#         u'uid': 294,         # Star ID
#         u'i': 3,             # Industry
#         u'puid': 5,          # Player ID
#         u'n': u'Sham',       # Name
#         u's': 2,             # Science
#         u'r': 40,            # Resources
#         u'exp': 0,
#         u'v': u'1',          # Visible
#         u'y': u'5.04934006', # y location
#         u'x': u'0.69888656', # x location
#         u'ga': 0,
#         u'st': 290           # Ships
#     }
class Star(object):
    ECONOMY = 'economy'
    INDUSTRY = 'industry'
    SCIENCE = 'science'

    def __init__(self, star_info):
        self.visible = int(star_info['v'])
        self.name = star_info['n']
        self.id = int(star_info['uid'])
        self.player_id = int(star_info['puid'])
        self.loc_x = float(star_info['x'])
        self.loc_y = float(star_info['y'])

        if self.visible:
            self.ships = int(star_info['st'])
            self.economy = int(star_info['e'])
            self.industry = int(star_info['i'])
            self.science = int(star_info['s'])
            self.resources = int(star_info['r'])

            e = self.economy + 1
            i = self.industry + 1
            s = self.science + 1
            self.costs = {
                Star.ECONOMY: math.floor(
                    (10.0 * e * e) / (self.resources / 100.0)),
                Star.INDUSTRY: math.floor(
                    (15.0 * i * i) / (self.resources / 100.0)),
                Star.SCIENCE: math.floor(
                    (20.0 * s * s) / (self.resources / 100.0)),
            }
        else:
            self.ships = None

    def distance_to(self, star):
        distance = math.sqrt(
            (self.loc_x - star.loc_x) ** 2 +
            (self.loc_y - star.loc_y) ** 2)
        return {
            'distance': distance * LIGHT_YEAR_SCALE,
            'time': int(math.ceil(distance * LIGHT_YEAR_SCALE * LIGHT_YEAR_TIME))
        }

    def upgrade(self, resource):
        amount = self.costs[resource]
        data = {'type': 'batched_orders',
                'order': 'upgrade_%s,%d,%d' % (resource, self.id, amount),
                'version': '',
                'game_number': '%d' % game_id}
        print("Star.upgrade(): command: %s" % data)

        result = requests.post(
            'https://np.ironhelmet.com/prequest/batched_orders',
            data=data,
            cookies=cookies)
        print('Star.upgrade(): status=%d text=%s' % (
        result.status_code, result.text))


class Stars(object):

    def __init__(self, stars):
        self.stars = stars

    @staticmethod
    def from_universe(universe):
        """Return an array of stars from the universe"""
        stars = []
        for star_id, star in universe['report']['stars'].items():
            stars.append(Star(star))
        return Stars(sorted(stars, key=lambda i: i.id))

    def stars_for_player(self, stars, player_id):
        return Stars([star for star in self.stars if star.player_id == player_id])

    def print_upgrades(self):
        print("Upgrade Costs:")

        cheapest_e = self.find_cheapest(Star.ECONOMY)
        cheapest_i = self.find_cheapest(Star.INDUSTRY)
        cheapest_s = self.find_cheapest(Star.SCIENCE)
        for star in sorted(self.stars, key=lambda i: i.name):
            print("%24s: id:%3d e:%5d%1s i:%5d%1s s:%5d%1s" % (
                star.name, star.id,
                star.costs[Star.ECONOMY], "*" if (star == cheapest_e) else " ",
                star.costs[Star.INDUSTRY], "*" if (star == cheapest_i) else " ",
                star.costs[Star.SCIENCE], "*" if (star == cheapest_s) else " "))

    def by_name(self, name):
        return next(star for star in self.stars if star.name == name)

    def by_id(self, id):
        return next(star for star in self.stars if star.id == id)

    def find_cheapest(self, resource):
        return sorted(self.stars, key=lambda i: i.costs[resource])[0]

    def upgrade_cheapest(self, resource, execute=False):
        star = self.find_cheapest(resource)
        print("Cheapest %s: %s - %d" % (resource, star.name, star.costs[resource]))

        if execute:
            star.upgrade(resource)


  # "50": {
  #   "uid": 50,
  #   "sp": 0.041666666666666664,
  #   "l": 0,
  #   "o": [
  #     [
  #       0,
  #       294,
  #       1,
  #       0
  #     ],
  #     [
  #       0,
  #       82,
  #       1,
  #       0
  #     ]
  #   ],
  #   "n": "Peacock I",
  #   "puid": 5,
  #   "exp": 140,
  #   "y": "4.96296426",
  #   "x": "0.71448864",
  #   "st": 3372,
  #   "lx": "0.72189505",
  #   "ly": "4.92196113"
  # },
class Fleet(object):
    pass

def main():

    options = handle_args()

    load_cookies(options.login, options.password, options.credentials)
    get_universe()

    player_id = universe['report']['player_uid']
    player_name = universe['report']['players'][str(player_id)]['alias']
    print(f"Player ID: {player_id}")
    print(f"Cash: {universe['report']['players'][str(player_id)]['cash']}")

    stars = Stars.from_universe(universe)
    player_stars = stars.stars_for_player(stars, player_id)

    print(f"Player {player_name} : {len(player_stars.stars)} stars")

    player_stars.print_upgrades()

    print(f'distance: {stars.by_name("Alnilam").distance_to(stars.by_name("Septen"))}')

    if options.upgrade_economy:
        player_stars.upgrade_cheapest(Star.ECONOMY, options.execute)
    if options.upgrade_industry:
        player_stars.upgrade_cheapest(Star.INDUSTRY, options.execute)
    if options.upgrade_science:
        player_stars.upgrade_cheapest(Star.SCIENCE, options.execute)


def console_init():
    load_cookies(None, None, "creds.np")
    get_universe(cookies, game_id)
    return cookies, universe


if __name__ == '__main__':
    main()