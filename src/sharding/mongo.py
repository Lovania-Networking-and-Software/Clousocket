import pymongo
import motor


class MongoSDS:
    def __init__(self, consul):
        self.consul = consul
