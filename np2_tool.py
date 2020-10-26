#!/usr/bin/env python3

import argparse
from enum import Enum
import json
import math
import os
import pickle
import requests
import sys
import time

from multiprocessing import Manager, Process

################################################################################
# Configurable
#
UNIVERSE_FILE = "universe.json"
PLAYERS_FILE = "players.json"

MONITOR_PERIOD = 5 * 60  # In seconds
MAX_DELAY = 60

UPGRADE_RESERVE = 850  # Amount of cash to reserve from automatic upgrades

################################################################################
# Constants
#

# 3 hours per LY
LIGHT_YEAR_TIME = 3

# 1 star scale = 8 light years observed
# docs say 1/16, but seem to be wrong
LIGHT_YEAR_SCALE = 8


def handle_args():
    global options

    parser = argparse.ArgumentParser()

    parser.add_argument("-l", "--login", help="Login ID")
    parser.add_argument("-p", "--password", help="password")
    parser.add_argument("-C", "--credentials", default="creds.np", help="Cookies output file [default: %(default)s]")
    parser.add_argument("-g", "--gameid", type=int, default=5380395345117184, help="Game ID")

    parser.add_argument("-v", "--verbose", action="store_true")

    parser.add_argument("-u", "--universe", action="store_true", help="Attempt to load universe.json before querying for universe")
    parser.add_argument("--ship_counts", action="store_true")
    parser.add_argument("-R", "--risk", action="store_true")

    parser.add_argument("-U", "--upgrade", action="store_true", help="Upgrade the cheapest available star resource")
    parser.add_argument("-E", "--upgrade_economy", action="store_true")
    parser.add_argument("-I", "--upgrade_industry", action="store_true")
    parser.add_argument("-S", "--upgrade_science", action="store_true")
    parser.add_argument("--execute", action="store_true")

    parser.add_argument("-M", "--monitor", action="store_true")

    options = parser.parse_args()

    if (not os.path.isfile(options.credentials)) and (options.login is None or options.password is None):
        print("Must provide cookies file or login/password")
        sys.exit(1)

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

    universe = None
    if options.universe and os.path.isfile(UNIVERSE_FILE):
        with open(UNIVERSE_FILE, "r") as fd:
            universe = json.load(fd)
            print(f"get_universe(): read universe from {UNIVERSE_FILE}")

    if not universe:
        print("get_universe(): querying for universe")
        response = requests.post('https://np.ironhelmet.com/trequest/order',
                                 data={'type':'order',
                                       'order':'full_universe_report',
                                       'version':'',
                                       'game_number':options.gameid},
                                 cookies=cookies)
        universe = response.json()
        if response.status_code != requests.codes.ok:
            print("get_universe(): request failed, code %d" % response.status_code)
            print("  data: %s" % response.text)
            sys.exit(1)

    if 'player_uid' not in universe['report']:
        print("get_universe(): invalid universe: %s" % (json.dumps(universe)))
        sys.exit()

    with open(UNIVERSE_FILE, "w") as f:
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

    def __init__(self, info):
        self.visible = int(info['v'])
        self.name = info['n']
        self.id = int(info['uid'])
        self.player_id = int(info['puid'])
        self.loc_x = float(info['x'])
        self.loc_y = float(info['y'])

        if self.visible:
            self.ships = int(info['st'])
            self.resources = {
                Star.ECONOMY: int(info['e']),
                Star.INDUSTRY: int(info['i']),
                Star.SCIENCE: int(info['s'])
            }
            self.size = int(info['r'])
            self.gate = int(info['ga'])

            self.costs = self.calculate_costs()
        else:
            self.ships = None

        # Wormhole
        if "wh" in info:
            self.wh = int(info['wh'])
        else:
            self.wh = None

    def calculate_costs(self):
        e = self.resources[Star.ECONOMY] + 1
        i = self.resources[Star.INDUSTRY] + 1
        s = self.resources[Star.SCIENCE] + 1
        return {
            Star.ECONOMY: math.floor(
                (10.0 * e * e) / (self.size / 100.0)),
            Star.INDUSTRY: math.floor(
                (15.0 * i * i) / (self.size / 100.0)),
            Star.SCIENCE: math.floor(
                (20.0 * s * s) / (self.size / 100.0)),
        }

    # TODO: This should probably take tech range levels into account?
    def distance_to(self, target):
        distance = math.sqrt(
            (self.loc_x - target.loc_x) ** 2 +
            (self.loc_y - target.loc_y) ** 2)

        if isinstance(target, Star) and target.wh and target.wh == self.id:
            hours = 24
        else:
            hours = int(math.ceil(distance * LIGHT_YEAR_SCALE * LIGHT_YEAR_TIME))

        return {
            'distance': distance * LIGHT_YEAR_SCALE,
            'time': hours
        }

    def upgrade(self, resource):
        amount = self.costs[resource]
        data = {'type': 'batched_orders',
                'order': 'upgrade_%s,%d,%d' % (resource, self.id, amount),
                'version': '',
                'game_number': '%d' % options.gameid}
        print("Star.upgrade(): command: %s" % data)

        result = requests.post(
            'https://np.ironhelmet.com/prequest/batched_orders',
            data=data,
            cookies=cookies)
        print('Star.upgrade(): status=%d text=%s' % (
            result.status_code, result.text))
        if result.status_code != 200:
            print(f"Star.upgrade(): failed, status={result.status_code}")
            return False
        response = result.json()
        if response["event"] != "order:ok":
            print(f"Star.upgrade(): failed '{response['report']}'")
            return False

        # Apply the upgrade to the model
        self.resources[resource] += 1
        self.costs = self.calculate_costs()

        return True

    def ships_in_range(self, stars, fleets, players, hours):
        counts = {
            Player.SELF: 0,
            Player.FRIEND: 0,
            Player.NEUTRAL: 0,
            Player.FOE:0
        }
        for star in stars:
            if star.visible:
                distance = self.distance_to(star)
                if distance['time'] <= hours:
                    player = players.by_id(star.player_id)
                    counts[player['state']] += star.ships
        for fleet in fleets:
            distance = self.distance_to(fleet)
            if distance['time'] <= hours:
                player = players.by_id(fleet.player_id)
                counts[player['state']] += fleet.ships

        return counts


class Stars(object):
    def __init__(self, stars):
        self.stars = stars

    @staticmethod
    def from_universe(universe):
        """Return an array of stars from the universe"""
        global stars
        star_array = []
        for star_id, star in universe['report']['stars'].items():
            star_array.append(Star(star))
        stars = Stars(sorted(star_array, key=lambda i: i.id))
        return stars

    def stars_for_player(self, stars, player_id):
        return Stars([star for star in self.stars if star.player_id == player_id])

    def print_upgrades(self):
        print("Upgrade Costs:")

        (resource, cheapest_e) = self.find_cheapest(Star.ECONOMY)
        (resource, cheapest_i) = self.find_cheapest(Star.INDUSTRY)
        (resource, cheapest_s) = self.find_cheapest(Star.SCIENCE)
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
        """
        Find the star with the cheapest upgrade cost
        :param resource: Resource type for cheapest, None for cheapest across all
        :return: (resource type, star)
        """
        if resource:
            return resource, sorted(self.stars, key=lambda i: i.costs[resource])[0]
        else:
            # Choose the cheapest of all resources, when equal prefer
            #     economy > industry > science
            (resource, star_e) = self.find_cheapest(Star.ECONOMY)
            (resource, star_i) = self.find_cheapest(Star.INDUSTRY)
            (resource, star_s) = self.find_cheapest(Star.SCIENCE)
            if (star_e.costs[Star.ECONOMY] <= star_i.costs[Star.INDUSTRY]) and (star_e.costs[Star.ECONOMY] <= star_s.costs[Star.SCIENCE]):
                return Star.ECONOMY, star_e
            elif star_i.costs[Star.INDUSTRY] <= star_s.costs[Star.SCIENCE]:
                return Star.INDUSTRY, star_i
            else:
                return Star.SCIENCE, star_s

    def upgrade_cheapest(self, resource, execute=False, cash=0):
        """
        Upgrade the cheapest resource
        :param resource: if resource is None then cheapest across types
        :param execute:
        :return:
        """
        (resource, star) = self.find_cheapest(resource)

        cost = star.costs[resource]
        print("Cheapest %s: %s - %d" % (resource, star.name, cost))

        if execute:
            if cash < cost:
                print(f"Inadequate funds for upgrade")
                return None, None, None
            if not star.upgrade(resource):
                return None, None, None
            print(f"Upgraded {star.name}: {resource} for {cost}")

        return resource, star, cost

    def ships_in_range(self):
        result = {}
        for hours in range(1, 25):
            for star in self.stars:
                ships = star.ships_in_range(stars, fleets, players, hours)
                if star.name not in result:
                    result[star.name] = {}
                result[star.name][hours] = ships
        return result

    def __iter__(self):
        return iter(self.stars)

    def __len__(self):
        return len(self.stars)


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
    def __init__(self, info):
        self.name = info['n']
        self.id = int(info['uid'])
        self.player_id = int(info['puid'])
        self.loc_x = float(info['lx'])
        self.loc_y = float(info['ly'])
        self.ships = int(info['st'])

    def __str__(self):
        return f"{self.name:>20}: id:{self.id:<3} ships:{self.ships:<5} player:{self.player_id}"


class Fleets(object):
    def __init__(self, fleets):
        self.fleets = fleets

    @staticmethod
    def from_universe(uni):
        """Return an array of fleets from the universe"""
        global fleets

        fleet_array = []
        for fleet_id, fleet in uni['report']['fleets'].items():
            fleet_array.append(Fleet(fleet))
        fleets = Fleets(sorted(fleet_array, key=lambda i: i.id))
        return fleets

    def __str__(self):
        return '\n'.join([str(s) for s in self.fleets])

    def __iter__(self):
        return iter(self.fleets)


class Player(dict):
    SELF = 0
    FRIEND = 1
    NEUTRAL = 2
    FOE = 3

    def __init__(self, player_info):
        dict.__init__(self,
                      name=player_info['alias'],
                      id=int(player_info['uid']),
                      state=Player.NEUTRAL)

    def relationship(self):
        if self['state'] == Player.SELF:
            return 'self'
        if self['state'] == Player.FRIEND:
            return 'friend'
        if self['state'] == Player.NEUTRAL:
            return 'neutral'
        if self['state'] == Player.FOE:
            return 'foe'

    def __str__(self):
        return f"{self['name']:>20}: id:{self['id']:<3} state:{self.relationship()}"


class Players(dict):
    def __init__(self, players):
        dict.__init__(self, players=players)

    def update_from_file(self):
        with open(PLAYERS_FILE, "r") as fd:
            players = json.load(fd)
            for p in players['players']:
                found = self.by_name(p['name'])
                found['state'] = p['state']

    @staticmethod
    def from_universe(uni):
        """Return an array of players from the universe"""
        global players

        player_array = []
        for player_id, player in uni['report']['players'].items():
            p = Player(player)
            if p['id'] == int(uni['report']['player_uid']):
                p['state'] = Player.SELF
            player_array.append(p)
        players = Players(sorted(player_array, key=lambda i: i['id']))

        if os.path.isfile(PLAYERS_FILE):
            players.update_from_file()

        players.to_file()

        return players

    def to_file(self):
        with open(PLAYERS_FILE, "w") as fd:
            json.dump(self, fd, indent=2, sort_keys=True)

    def by_name(self, name):
        return next(player for player in self['players'] if player['name'] == name)

    def by_id(self, id):
        return next(player for player in self['players'] if player['id'] == id)

    def __str__(self):
        return '\n'.join([str(s) for s in self['players']])


def monitor_process(opt, creds):
    global options
    global cookies
    options = opt
    cookies = creds

    print("Launching monitor process")

    while True:
        start_time = time.time()
        get_universe()
        player_id = universe['report']['player_uid']
        cash = universe['report']['players'][str(player_id)]['cash']
        Stars.from_universe(universe)
        player_stars = stars.stars_for_player(stars, player_id)

        # Upgrade all cheapest
        while cash > 0:
            # Determine how much if available to spend after reserved amount
            available = cash - UPGRADE_RESERVE if (cash - UPGRADE_RESERVE > 0) else 0
            print(f"Player has ${cash} remaining, ${available} available")

            resource, star, cost = player_stars.upgrade_cheapest(None,
                                                                 execute=True,
                                                                 cash=available)
            if resource is None:
                break
            cash -= cost
            time.sleep(1)

        while True:
            now = time.time()
            delay = MONITOR_PERIOD - (now - start_time)
            if delay < 0:
                break
            print(f"Sleeping for {delay:.0f} seconds")
            time.sleep(min(delay, MAX_DELAY))

    print("Exiting monitor process")
    return


def main():
    handle_args()

    load_cookies(options.login, options.password, options.credentials)
    get_universe()

    player_id = universe['report']['player_uid']
    player_name = universe['report']['players'][str(player_id)]['alias']
    print(f"Player ID: {player_id}")

    cash = universe['report']['players'][str(player_id)]['cash']
    print(f"Cash: {cash}")

    Stars.from_universe(universe)
    player_stars = stars.stars_for_player(stars, player_id)

    print(f"Player {player_name} : {len(player_stars.stars)} stars")

    player_stars.print_upgrades()

    Players.from_universe(universe)
    print(f"Players:\n{players}")
    player = players.by_id(player_id)

    Fleets.from_universe(universe)
    print(f"Fleets:\n{fleets}")

    if options.ship_counts or options.risk:
        ranges = player_stars.ships_in_range()
        hours = ""
        for star, data in ranges.items():
            txt = f"{star:>24}: "
            for hour, ships in data.items():
                risk = ships[Player.FOE] - ships[Player.SELF]
                if risk < 0:
                    risk = 0
                if options.risk:
                    txt += f"{risk:<5} "
                else:
                    txt += f"{ships[Player.FOE]:<5} "
                if hours is not None:
                    hours += f"{hour:<5} "
            if hours is not None:
                print(f"{'Ships in range - hours':>24}: {hours}")
                hours = None
            print(txt)

    if options.upgrade:
        player_stars.upgrade_cheapest(None, options.execute, cash)
    if options.upgrade_economy:
        player_stars.upgrade_cheapest(Star.ECONOMY, options.execute, cash)
    if options.upgrade_industry:
        player_stars.upgrade_cheapest(Star.INDUSTRY, options.execute, cash)
    if options.upgrade_science:
        player_stars.upgrade_cheapest(Star.SCIENCE, options.execute, cash)

    if options.monitor:
        upgrade_monitor = Process(target=monitor_process,
                                  args=(options, cookies),
                                  kwargs={})
        upgrade_monitor.start()
        upgrade_monitor.join()


def console_init():
    """
    Execute this to setup environment if running from the python interactive
    console.
    :return: (cookies, universe)
    """
    load_cookies(None, None, "creds.np")
    get_universe()
    Stars.from_universe(universe)
    Players.from_universe(universe)
    Fleets.from_universe(universe)
    return cookies, universe


if __name__ == '__main__':
    main()