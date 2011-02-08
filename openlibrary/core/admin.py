"""Admin functionality.
"""

import datetime

import couchdb

from infogami import config


class Stats:
    def __init__(self, docs = None, key = None):
        if docs == None and key == None:
            self.stats = range(0, 150, 5)
        else:
            self.stats = [x[key] for x in docs]
        print "Stats for %s"%key
        print self.stats
        
    def get_counts(self, ndays = 30):
        """Returns the stats for last n days as an array."""
        retval = zip(range(0, ndays*5, 5), self.stats) # The *5 and 5 are for the bar widths
        print "Retval is ", retval
        return retval
        
    def get_summary(self, ndays = 30):
        """Returns the summary of counts for past n days.
        
        Summary can be either sum or average depending on the type of stats.
        This is used to find counts for last 7 days and last 28 days.
        """
        return sum(x[1] for x in self.get_counts(ndays))
        
    def get_total(self):
        """Returns the total counts."""
        return 0


            
def get_stats():
    """Returns the stats 
    """
    admin_db = couchdb.Database(config.admin.counts_db)
    end      = datetime.datetime.now().strftime("counts-%Y-%m-%d")
    start    = (datetime.datetime.now() - datetime.timedelta(days = 30)).strftime("counts-%Y-%m-%d")
    print start
    print end
    docs = [x.doc for x in admin_db.view("_all_docs",
                                         startkey_docid = start,
                                         endkey_docid   = end,
                                         include_docs = True)]

    retval = dict(edits = Stats(docs, "human_edits"),
                  lists = Stats(docs, "lists")
                  )

    print "Main get_stats() ", retval["edits"].get_counts(30)
    return retval
    
