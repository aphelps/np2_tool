from neptune.Fleet import Fleet


class Fleets(object):
    def __init__(self, fleets, universe):
        self.fleets = fleets
        self.universe = universe

    @staticmethod
    def from_universe(universe):
        """Return an array of fleets from the universe"""
        fleet_array = []
        for fleet_id, fleet in universe.data['report']['fleets'].items():
            fleet_array.append(Fleet(fleet))
        fleets = Fleets(sorted(fleet_array, key=lambda i: i.id), universe)
        return fleets

    def __str__(self):
        return '\n'.join([str(s) for s in self.fleets])

    def __iter__(self):
        return iter(self.fleets)

    def __len__(self):
        return len(self.fleets)

