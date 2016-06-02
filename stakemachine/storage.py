from pymongo import MongoClient
import os
import json


class InvalidStorageType(Exception):
    pass


class Storage(object):
    """ This class simplifies the Storage of bots' states in a JSON-file
        or a mongo database
    """
    def __init__(self, name, config, *args, **kwargs):
        self.name = name
        self.filename = "data_%s.json" % self.name
        if not hasattr(config, "storage"):
            setattr(config, "storage", "json")
        self.config = config

        if self.config.storage == "json":
            pass
        elif self.config.storage == "mongo":
            if not hasattr(config, "mongo_server"):
                raise ValueError("Need configuration 'mongo_server'!")

            self.client = MongoClient(config.mongo_server)
            collection = config.mongo_server.split("/")[-1]
            self.db = self.client[collection]
        else:
            raise InvalidStorageType

    def restore(self):
        r = None
        if self.config.storage == "json":
            if os.path.isfile(self.filename) :
                with open(self.filename, 'r') as fp:
                    try:
                        r = json.load(fp)
                    except:
                        r = {}
        elif self.config.storage == "mongo":
            r = self.db.config.find_one({"name": self.name})
        if not r:
            r = {}
        if not "orders" in r:
            r["orders"] = {}
        return r

    def store(self, state):
        if self.config.storage == "json":
            with open(self.filename, 'w') as fp:
                json.dump(state, fp)
        elif self.config.storage == "mongo":
            result = self.db.states.update_one(
                {"name": self.name},
                {"$set": state,
                 }, True)
            return result.matched_count
