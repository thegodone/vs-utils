"""
IPython.parallel utilities.
"""

__author__ = "Steven Kearnes"
__copyright__ = "Copyright 2014, Stanford University"
__license__ = "BSD 3-clause"

import subprocess
import time
import uuid


class LocalCluster(object):
    """
    Run an IPython.parallel cluster on localhost.

    Parameters
    ----------
    n_engines : int
        Number of engines to initialize.
    """
    def __init__(self, n_engines):
        self.n_engines = n_engines

        # placeholders
        self.cluster_id = None
        self.controller = None
        self.engines = []
        self.output = None

        # initialize the cluster
        self.start()

    def __del__(self):
        """
        Shut down the cluster.
        """
        self.stop()

    def start(self):
        """
        Start the cluster by running ipcontroller and ipengine.
        """
        self.cluster_id = uuid.uuid4()
        self.controller = subprocess.Popen(
            ['ipcontroller', '--cluster-id={}'.format(self.cluster_id),
             '--log-level=ERROR'])
        time.sleep(1)  # wait for controller to initialize
        for i in xrange(self.n_engines):
            engine = subprocess.Popen(
                ['ipengine', '--cluster-id={}'.format(self.cluster_id),
                 '--log-level=ERROR'])
            self.engines.append(engine)
        time.sleep(10)  # wait for engines to initialize

    def stop(self):
        """
        Shut down the cluster.
        """
        for engine in self.engines:
            engine.terminate()
        self.controller.terminate()
