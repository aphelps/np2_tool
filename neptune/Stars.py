from neptune.Star import Star


class Stars(object):
    def __init__(self, stars, universe):
        self.stars = stars
        self.universe = universe

    @staticmethod
    def from_universe(universe):
        """Return an array of stars from the universe"""
        star_array = []
        for star_id, star in universe.data['report']['stars'].items():
            star_array.append(Star(star, universe))
        stars = Stars(sorted(star_array, key=lambda i: i.id), universe)
        return stars

    def stars_for_player(self, player):
        return Stars([star for star in self.stars if star.player_id == player['id']],
                     self.universe)

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
        :param cash:
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
                ships = star.ships_in_range(self, self.universe.fleets,
                                            self.universe.players, hours)
                if star.name not in result:
                    result[star.name] = {}
                result[star.name][hours] = ships
        return result

    def __iter__(self):
        return iter(self.stars)

    def __len__(self):
        return len(self.stars)