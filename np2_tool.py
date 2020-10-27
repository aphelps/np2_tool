#!/usr/bin/env python3

import argparse
import os
import sys
import time

from neptune.Player import Player
from neptune.Star import Star
from neptune.State import State
from neptune.Universe import Universe

from multiprocessing import Process

################################################################################
# Configurable
#

MONITOR_PERIOD = 15 * 60  # In seconds
MAX_DELAY = 60

UPGRADE_RESERVE_DEFAULT = 1000  # Amount of cash to reserve from automatic upgrades


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
    parser.add_argument("-r", "--reserve", type=int, default=UPGRADE_RESERVE_DEFAULT,
                        help="Cash to hold back from automatic updates [default: %(default)d]")

    options = parser.parse_args()

    if (not os.path.isfile(options.credentials)) and (options.login is None or options.password is None):
        print("Must provide cookies file or login/password")
        sys.exit(1)

    return options


def monitor_process(options, state):

    print("Launching monitor process")

    while True:
        start_time = time.time()
        universe = Universe.get_universe(options.universe, state)

        player = universe.player()
        cash = universe.cash()
        player_stars = universe.stars.stars_for_player(player)

        time_to_tick = universe.seconds_to_tick()

        print(f"\n{'*' * 60}")
        print(f"Player {player['name']}/{player['id']}: ${cash}, {time_to_tick / 60:.0f}:{time_to_tick % 60:.0f} to tick")

        # Upgrade all cheapest
        while cash > 0:
            # Determine how much if available to spend after reserved amount
            available = cash - options.reserve if (cash - options.reserve > 0) else 0
            print(f"Player has ${cash} remaining, ${available} available")

            resource, star, cost = player_stars.upgrade_cheapest(None,
                                                                 execute=options.execute,
                                                                 cash=available)
            if resource is None:
                break
            cash -= cost
            time.sleep(1)

        while True:
            now = time.time()
            delay = MONITOR_PERIOD - (now - start_time)
            delay = min(delay, (universe.tick_time + 15 - now))
            if delay < 0:
                break
            print(f"Sleeping for {delay:.0f}s, {universe.tick_time - now:.0f}s to tick")
            time.sleep(min(delay, MAX_DELAY))

    print("Exiting monitor process")
    return


def main():
    handle_args()

    state = State.new(options.login, options.password, options.credentials,
                      options.gameid)
    universe = Universe.get_universe(options.universe, state)

    player = universe.player()
    print(f"Player Name: {player['name']} ID: {player['id']}")
    print(f"Cash: {universe.cash()}")

    player_stars = universe.stars.stars_for_player(player)

    print(f"\nPlayer {player['name']}: {len(player_stars.stars)} stars")
    player_stars.print_upgrades()

    print(f"\nPlayers: {len(universe.players)}\n{universe.players}")
    print(f"\nFleets: {len(universe.fleets)}\n{universe.fleets}")

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
        player_stars.upgrade_cheapest(None, options.execute, universe.cash())
    if options.upgrade_economy:
        player_stars.upgrade_cheapest(Star.ECONOMY, options.execute, universe.cash())
    if options.upgrade_industry:
        player_stars.upgrade_cheapest(Star.INDUSTRY, options.execute, universe.cash())
    if options.upgrade_science:
        player_stars.upgrade_cheapest(Star.SCIENCE, options.execute, universe.cash())

    if options.monitor:
        upgrade_monitor = Process(target=monitor_process,
                                  args=(options, state),
                                  kwargs={})
        upgrade_monitor.start()
        upgrade_monitor.join()


def console_init():
    """
    Execute this to setup environment if running from the python interactive
    console.
    :return: (cookies, universe)
    """
    state = State.new(None, None, "creds.np", None)
    universe = Universe.get_universe(True, state)
    return state, universe


if __name__ == '__main__':
    main()