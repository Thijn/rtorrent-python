# Copyright (c) 2012 Chris Lucas, <chris@chrisjlucas.com>
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
# 
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import rtorrent.rpc
#from rtorrent.rpc import Method
import rtorrent.peer
import rtorrent.tracker
import rtorrent.file

Peer = rtorrent.peer.Peer
Tracker = rtorrent.tracker.Tracker
File = rtorrent.file.File
Method = rtorrent.rpc.Method

class Torrent:
    """Represents an individual torrent within a L{RTorrent} instance."""

    def __init__(self, _rt_obj, info_hash, **kwargs):
        self._rt_obj = _rt_obj
        self.info_hash = info_hash #: info hash for the torrent
        self.rpc_id = self.info_hash #: unique id to pass to rTorrent
        for k in kwargs.keys():
            setattr(self, k.replace(".", "_"), kwargs.get(k, None))

        self.peers = []
        self.trackers = []
        self.files = []

        self._call_custom_methods()

    def __repr__(self):
        return("<Torrent info_hash=\"{0}\" name=\"{1}\">".format(
                                                            self.info_hash,
                                                            self.name))

    def _call_custom_methods(self):
        """only calls methods that check instance variables."""
        self.is_hash_checking_queued()
        self.is_started()
        self.is_paused()

    def get_peers(self):
        """Get list of Peer instances for given torrent.

        @return: L{Peer} instances
        @rtype: list

        @note: also assigns return value to self.peers
        """
        self.peers = []
        retriever_methods = [m for m in rtorrent.peer.methods \
                        if m.is_retriever() and m.is_available(self._rt_obj)]
        # need to leave 2nd arg empty (dunno why)
        m = rtorrent.rpc.Multicall(self)
        m.add("p.multicall", self.info_hash, "",
                *[method.rpc_call + "=" for method in retriever_methods])

        results = m.call()[0] # only sent one call, only need first result

        for result in results:
            results_dict = {}
            # build results_dict
            for m, r in zip(retriever_methods, result):
                results_dict[m.varname] = rtorrent.rpc.process_result(m, r)

            self.peers.append(Peer(self._rt_obj, self.info_hash, **results_dict))

        return(self.peers)

    def get_trackers(self):
        """Get list of Tracker instances for given torrent.

        @return: L{Tracker} instances
        @rtype: list
        
        @note: also assigns return value to self.trackers
        """
        self.trackers = []
        retriever_methods = [m for m in rtorrent.tracker.methods \
                        if m.is_retriever() and m.is_available(self._rt_obj)]

        # need to leave 2nd arg empty (dunno why)
        m = rtorrent.rpc.Multicall(self)
        m.add("t.multicall", self.info_hash, "",
                *[method.rpc_call + "=" for method in retriever_methods])

        results = m.call()[0] # only sent one call, only need first result

        for result in results:
            results_dict = {}
            # build results_dict
            for m, r in zip(retriever_methods, result):
                results_dict[m.varname] = rtorrent.rpc.process_result(m, r)

            self.trackers.append(Tracker(self._rt_obj, self.info_hash, **results_dict))

        return(self.trackers)

    def get_files(self):
        """Get list of File instances for given torrent.

        @return: L{File} instances
        @rtype: list

        @note: also assigns return value to self.files
        """

        self.files = []
        retriever_methods = [m for m in rtorrent.file.methods \
                        if m.is_retriever() and m.is_available(self._rt_obj)]
        # 2nd arg can be anything, but it'll return all files in torrent regardless
        m = rtorrent.rpc.Multicall(self)
        m.add("f.multicall", self.info_hash, "",
                *[method.rpc_call + "=" for method in retriever_methods])

        results = m.call()[0] # only sent one call, only need first result

        offset_method_index = retriever_methods.index(
                                    rtorrent.rpc.find_method("f.get_offset"))

        # make a list of the offsets of all the files, sort appropriately
        offset_list = sorted([r[offset_method_index] for r in results])

        for result in results:
            results_dict = {}
            # build results_dict
            for m, r in zip(retriever_methods, result):
                results_dict[m.varname] = rtorrent.rpc.process_result(m, r)

            # get proper index positions for each file (based on the file offset)
            f_index = offset_list.index(results_dict["offset"])

            self.files.append(File(self._rt_obj, self.info_hash, \
                                   f_index, **results_dict))

        return(self.files)

    def set_directory(self, d):
        """Modify download directory
        
        @note: Needs to stop torrent in order to change the directory.
        Also doesn't restart after directory is set, that must be called
        separately.
        """
        m = rtorrent.rpc.Multicall(self)
        self.multicall_add(m, "d.try_stop")
        self.multicall_add(m, "d.set_directory", d)

        self.directory = m.call()[-1]

    def start(self):
        """Start the torrent"""
        m = rtorrent.rpc.Multicall(self)
        self.multicall_add(m, "d.try_start")
        self.multicall_add(m, "d.is_active")

        self.active = m.call()[-1]
        return(self.active)

    def stop(self):
        """"Stop the torrent"""
        m = rtorrent.rpc.Multicall(self)
        self.multicall_add(m, "d.try_stop")
        self.multicall_add(m, "d.is_active")

        self.active = m.call()[-1]
        return(self.active)

    def close(self):
        """Close the torrent and it's files"""
        m = rtorrent.rpc.Multicall(self)
        self.multicall_add(m, "d.close")

        return(m.call()[-1])

    def erase(self):
        """Delete the torrent
        
        @note: doesn't delete the downloaded files"""
        m = rtorrent.rpc.Multicall(self)
        self.multicall_add(m, "d.erase")

        return(m.call()[-1])

    def check_hash(self):
        """(Re)hash check the torrent"""
        m = rtorrent.rpc.Multicall(self)
        self.multicall_add(m, "d.check_hash")

        return(m.call()[-1])

    def poll(self):
        """poll rTorrent to get latest peer/tracker/file information"""
        self.get_peers()
        self.get_trackers()
        self.get_files()

    def update(self):
        """Refresh torrent data
        
        @note: All fields are stored as attributes to self.

        @return: None
        """
        multicall = rtorrent.rpc.Multicall(self)
        retriever_methods = [m for m in methods \
                        if m.is_retriever() and m.is_available(self._rt_obj)]
        for method in retriever_methods:
            multicall.add(method, self.rpc_id)

        multicall.call()

        # custom functions (only call private methods, since they only check
        # local variables and are therefore faster)
        self._call_custom_methods()

    def accept_seeders(self, accept_seeds):
        """Enable/disable whether the torrent connects to seeders
        
        @param accept_seeds: enable/disable accepting seeders 
        @type accept_seeds: bool"""
        if accept_seeds: call = "d.accepting_seeders.enable"
        else: call = "d.accepting_seeders.disable"

        m = rtorrent.rpc.Multicall(self)
        self.multicall_add(m, call)

        return(m.call()[-1])

    def announce(self):
        """Announce torrent info to tracker(s)"""
        m = rtorrent.rpc.Multicall(self)
        self.multicall_add(m, "d.tracker_announce")

        return(m.call()[-1])

    ############################################################################
    # CUSTOM METHODS (Not part of the official rTorrent API)
    ############################################################################
    def _is_hash_checking_queued(self):
        """Only checks instance variables, shouldn't be called directly"""
        # if hashing == 3, then torrent is marked for hash checking
        # if hash_checking == False, then torrent is waiting to be checked
        self.hash_checking_queued = (self.hashing == 3 and \
                                     self.hash_checking == False)

        return(self.hash_checking_queued)

    def is_hash_checking_queued(self):
        """Check if torrent is waiting to be hash checked
        
        @note: Variable where the result for this method is stored Torrent.hash_checking_queued"""
        m = rtorrent.rpc.Multicall(self)
        self.multicall_add(m, "d.hashing")
        self.multicall_add(m, "d.is_hash_checking")
        results = m.call()

        setattr(self, "hashing", results[0])
        setattr(self, "hash_checking", results[1])

        return(self._is_hash_checking_queued())

    def _is_paused(self):
        """Only checks instance variables, shouldn't be called directly"""
        self.paused = (self.state == 0)
        return(self.paused)

    def is_paused(self):
        """Check if torrent is paused
        
        @note: Variable where the result for this method is stored: Torrent.paused"""
        self.get_state()
        return(self._is_paused())

    def _is_started(self):
        """Only checks instance variables, shouldn't be called directly"""
        self.started = (self.state == 1)
        return(self.started)

    def is_started(self):
        """Check if torrent is started
        
        @note: Variable where the result for this method is stored: Torrent.started"""
        self.get_state()
        return(self._is_started())


methods = [
    # RETRIEVERS
    Method(Torrent, 'is_hash_checked', 'd.is_hash_checked',
           boolean=True,
           ),
    Method(Torrent, 'is_hash_checking', 'd.is_hash_checking',
           boolean=True,
           ),
    Method(Torrent, 'get_peers_max', 'd.peers_max'),
    Method(Torrent, 'get_tracker_focus', 'd.tracker_focus'),
    Method(Torrent, 'get_skip_total', 'd.skip.total'),
    Method(Torrent, 'get_state', 'd.state'),
    Method(Torrent, 'get_peer_exchange', 'd.peer_exchange'),
    Method(Torrent, 'get_down_rate', 'd.down_rate'),
    Method(Torrent, 'get_connection_seed', 'd.connection_seed'),
    Method(Torrent, 'get_uploads_max', 'd.uploads_max'),
    Method(Torrent, 'get_priority_str', 'd.priority_str'),
    Method(Torrent, 'is_open', 'd.is_open',
           boolean=True,
           ),
    Method(Torrent, 'get_peers_min', 'd.peers_min'),
    Method(Torrent, 'get_peers_complete', 'd.peers_complete'),
    Method(Torrent, 'get_tracker_numwant', 'd.tracker_numwant'),
    Method(Torrent, 'get_connection_current', 'd.connection_current'),
    Method(Torrent, 'is_complete', 'd.complete',
           boolean=True,
           ),
    Method(Torrent, 'get_peers_connected', 'd.peers_connected'),
    Method(Torrent, 'get_chunk_size', 'd.chunk_size'),
    Method(Torrent, 'get_state_counter', 'd.state_counter'),
    Method(Torrent, 'get_base_filename', 'd.base_filename'),
    Method(Torrent, 'get_state_changed', 'd.state_changed'),
    Method(Torrent, 'get_peers_not_connected', 'd.peers_not_connected'),
    Method(Torrent, 'get_directory', 'd.directory'),
    Method(Torrent, 'is_incomplete', 'd.incomplete',
           boolean=True,
           ),
    Method(Torrent, 'get_tracker_size', 'd.tracker_size'),
    Method(Torrent, 'is_multi_file', 'd.is_multi_file',
           boolean=True,
           ),
    Method(Torrent, 'get_local_id', 'd.local_id'),
    Method(Torrent, 'get_ratio', 'd.ratio',
           post_process_func=lambda x: x / 1000.0,
           ),
    Method(Torrent, 'get_loaded_file', 'd.loaded_file'),
    Method(Torrent, 'get_max_file_size', 'd.max_file_size'),
    Method(Torrent, 'get_size_chunks', 'd.size_chunks'),
    Method(Torrent, 'is_pex_active', 'd.is_pex_active',
           boolean=True,
           ),
    Method(Torrent, 'get_hashing', 'd.hashing'),
    Method(Torrent, 'get_bitfield', 'd.bitfield'),
    Method(Torrent, 'get_local_id_html', 'd.local_id_html'),
    Method(Torrent, 'get_connection_leech', 'd.connection_leech'),
    Method(Torrent, 'get_peers_accounted', 'd.peers_accounted'),
    Method(Torrent, 'get_message', 'd.message'),
    Method(Torrent, 'is_active', 'd.is_active',
           boolean=True,
           ),
    Method(Torrent, 'get_size_bytes', 'd.size_bytes'),
    Method(Torrent, 'get_up_total', 'd.up.total'),
    Method(Torrent, 'get_ignore_commands', 'd.ignore_commands'),
    Method(Torrent, 'get_creation_date', 'd.creation_date'),
    Method(Torrent, 'get_base_path', 'd.base_path'),
    Method(Torrent, 'get_left_bytes', 'd.left_bytes'),
    Method(Torrent, 'get_size_files', 'd.size_files'),
    Method(Torrent, 'get_size_pex', 'd.size_pex'),
    Method(Torrent, 'is_private', 'd.is_private',
           boolean=True,
           ),
    Method(Torrent, 'get_max_size_pex', 'd.max_size_pex'),
    Method(Torrent, 'get_num_chunks_hashed', 'd.chunks_hashed',
           aliases=("get_chunks_hashed",)),
    Method(Torrent, 'get_num_chunks_wanted', 'd.wanted_chunks'),
    Method(Torrent, 'get_priority', 'd.priority'),
    Method(Torrent, 'get_skip_rate', 'd.skip_rate'),
    Method(Torrent, 'get_completed_bytes', 'd.completed_bytes'),
    Method(Torrent, 'get_name', 'd.name'),
    Method(Torrent, 'get_completed_chunks', 'd.completed_chunks'),
    Method(Torrent, 'get_throttle_name', 'd.throttle_name'),
    Method(Torrent, 'get_free_diskspace', 'd.free_diskspace'),
    Method(Torrent, 'get_directory_base', 'd.directory_base'),
    Method(Torrent, 'get_hashing_failed', 'd.hashing_failed'),
    Method(Torrent, 'get_tied_to_file', 'd.tied_to_file'),
    Method(Torrent, 'get_down_total', 'd.down_total'),
    Method(Torrent, 'get_bytes_done', 'd.bytes_done'),
    Method(Torrent, 'get_up_rate', 'd.up_rate'),
    Method(Torrent, 'get_up_total', 'd.up_total'),
    Method(Torrent, 'is_accepting_seeders', 'd.accepting_seeders',
           boolean=True,
           ),
    Method(Torrent, "get_chunks_seen", "d.chunks_seen",
           min_version=(0, 9, 1),
           ),
    Method(Torrent, "is_partially_done", "d.is_partially_done",
           boolean=True,
           ),
    Method(Torrent, "is_not_partially_done", "d.is_not_partially_done",
           boolean=True,
           ),
    Method(Torrent, "get_time_started", "d.timestamp.started"),

    # MODIFIERS
    Method(Torrent, 'set_uploads_max', 'd.uploads_max.set'),
    Method(Torrent, 'set_tied_to_file', 'd.tied_to_file.set'),
    Method(Torrent, 'set_tracker_numwant', 'd.tracker_numwant.set'),
    Method(Torrent, 'set_custom', 'd.custom.set'),
    Method(Torrent, 'set_priority', 'd.priority.set'),
    Method(Torrent, 'set_peers_max', 'd.peers_max.set'),
    Method(Torrent, 'set_hashing_failed', 'd.hashing_failed.set'),
    Method(Torrent, 'set_message', 'd.message.set'),
    Method(Torrent, 'set_throttle_name', 'd.throttle_name.set'),
    Method(Torrent, 'set_peers_min', 'd.peers_min.set'),
    Method(Torrent, 'set_ignore_commands', 'd.ignore_commands.set'),
    Method(Torrent, 'set_max_file_size', 'd.max_file_size.set'),
    Method(Torrent, 'set_custom5', 'd.custom5.set'),
    Method(Torrent, 'set_custom4', 'd.custom4.set'),
    Method(Torrent, 'set_custom2', 'd.custom2.set'),
    Method(Torrent, 'set_custom1', 'd.custom1.set'),
    Method(Torrent, 'set_custom3', 'd.custom3.set'),
    Method(Torrent, 'set_connection_current', 'd.connection_current.set'),
]
