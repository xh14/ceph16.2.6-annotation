# -*- coding: utf-8 -*-
import uuid
from contextlib import contextmanager
from typing import Any, Dict, List, Optional
from unittest import mock

from ceph.deployment.drive_group import DeviceSelection, DriveGroupSpec  # type: ignore
from ceph.deployment.service_spec import PlacementSpec  # type: ignore

from .. import mgr
from ..controllers.osd import Osd
from ..tools import NotificationQueue, TaskManager
from . import ControllerTestCase  # pylint: disable=no-name-in-module
from .helper import update_dict  # pylint: disable=import-error


class OsdHelper(object):
    DEFAULT_OSD_IDS = [0, 1, 2]

    @staticmethod
    def _gen_osdmap_tree_node(node_id: int, node_type: str, children: Optional[List[int]] = None,
                              update_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        assert node_type in ['root', 'host', 'osd']
        if node_type in ['root', 'host']:
            assert children is not None

        node_types = {
            'root': {
                'id': node_id,
                'name': 'default',
                'type': 'root',
                'type_id': 10,
                'children': children,
            },
            'host': {
                'id': node_id,
                'name': 'ceph-1',
                'type': 'host',
                'type_id': 1,
                'pool_weights': {},
                'children': children,
            },
            'osd': {
                'id': node_id,
                'device_class': 'hdd',
                'type': 'osd',
                'type_id': 0,
                'crush_weight': 0.009796142578125,
                'depth': 2,
                'pool_weights': {},
                'exists': 1,
                'status': 'up',
                'reweight': 1.0,
                'primary_affinity': 1.0,
                'name': 'osd.{}'.format(node_id),
            }
        }
        node = node_types[node_type]

        return update_dict(node, update_data) if update_data else node

    @staticmethod
    def _gen_osd_stats(osd_id: int, update_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        stats = {
            'osd': osd_id,
            'up_from': 11,
            'seq': 47244640581,
            'num_pgs': 50,
            'kb': 10551288,
            'kb_used': 1119736,
            'kb_used_data': 5504,
            'kb_used_omap': 0,
            'kb_used_meta': 1048576,
            'kb_avail': 9431552,
            'statfs': {
                'total': 10804518912,
                'available': 9657909248,
                'internally_reserved': 1073741824,
                'allocated': 5636096,
                'data_stored': 102508,
                'data_compressed': 0,
                'data_compressed_allocated': 0,
                'data_compressed_original': 0,
                'omap_allocated': 0,
                'internal_metadata': 1073741824
            },
            'hb_peers': [0, 1],
            'snap_trim_queue_len': 0,
            'num_snap_trimming': 0,
            'op_queue_age_hist': {
                'histogram': [],
                'upper_bound': 1
            },
            'perf_stat': {
                'commit_latency_ms': 0.0,
                'apply_latency_ms': 0.0,
                'commit_latency_ns': 0,
                'apply_latency_ns': 0
            },
            'alerts': [],
        }
        return stats if not update_data else update_dict(stats, update_data)

    @staticmethod
    def _gen_osd_map_osd(osd_id: int) -> Dict[str, Any]:
        return {
            'osd': osd_id,
            'up': 1,
            'in': 1,
            'weight': 1.0,
            'primary_affinity': 1.0,
            'last_clean_begin': 0,
            'last_clean_end': 0,
            'up_from': 5,
            'up_thru': 21,
            'down_at': 0,
            'lost_at': 0,
            'public_addrs': {
                'addrvec': [{
                    'type': 'v2',
                    'nonce': 1302,
                    'addr': '172.23.0.2:6802'
                }, {
                    'type': 'v1',
                    'nonce': 1302,
                    'addr': '172.23.0.2:6803'
                }]
            },
            'cluster_addrs': {
                'addrvec': [{
                    'type': 'v2',
                    'nonce': 1302,
                    'addr': '172.23.0.2:6804'
                }, {
                    'type': 'v1',
                    'nonce': 1302,
                    'addr': '172.23.0.2:6805'
                }]
            },
            'heartbeat_back_addrs': {
                'addrvec': [{
                    'type': 'v2',
                    'nonce': 1302,
                    'addr': '172.23.0.2:6808'
                }, {
                    'type': 'v1',
                    'nonce': 1302,
                    'addr': '172.23.0.2:6809'
                }]
            },
            'heartbeat_front_addrs': {
                'addrvec': [{
                    'type': 'v2',
                    'nonce': 1302,
                    'addr': '172.23.0.2:6806'
                }, {
                    'type': 'v1',
                    'nonce': 1302,
                    'addr': '172.23.0.2:6807'
                }]
            },
            'state': ['exists', 'up'],
            'uuid': str(uuid.uuid4()),
            'public_addr': '172.23.0.2:6803/1302',
            'cluster_addr': '172.23.0.2:6805/1302',
            'heartbeat_back_addr': '172.23.0.2:6809/1302',
            'heartbeat_front_addr': '172.23.0.2:6807/1302',
            'id': osd_id,
        }

    @classmethod
    def gen_osdmap(cls, ids: Optional[List[int]] = None) -> Dict[str, Any]:
        return {str(i): cls._gen_osd_map_osd(i) for i in ids or cls.DEFAULT_OSD_IDS}

    @classmethod
    def gen_osd_stats(cls, ids: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        return [cls._gen_osd_stats(i) for i in ids or cls.DEFAULT_OSD_IDS]

    @classmethod
    def gen_osdmap_tree_nodes(cls, ids: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        return [
            cls._gen_osdmap_tree_node(-1, 'root', [-3]),
            cls._gen_osdmap_tree_node(-3, 'host', ids or cls.DEFAULT_OSD_IDS),
        ] + [cls._gen_osdmap_tree_node(node_id, 'osd') for node_id in ids or cls.DEFAULT_OSD_IDS]

    @classmethod
    def gen_mgr_get_counter(cls) -> List[List[int]]:
        return [[1551973855, 35], [1551973860, 35], [1551973865, 35], [1551973870, 35]]


class OsdTest(ControllerTestCase):
    @classmethod
    def setup_server(cls):
        Osd._cp_config['tools.authenticate.on'] = False  # pylint: disable=protected-access
        cls.setup_controllers([Osd])
        NotificationQueue.start_queue()
        TaskManager.init()

    @classmethod
    def tearDownClass(cls):
        NotificationQueue.stop()

    @contextmanager
    def _mock_osd_list(self, osd_stat_ids, osdmap_tree_node_ids, osdmap_ids):
        def mgr_get_replacement(*args, **kwargs):
            method = args[0] or kwargs['method']
            if method == 'osd_stats':
                return {'osd_stats': OsdHelper.gen_osd_stats(osd_stat_ids)}
            if method == 'osd_map_tree':
                return {'nodes': OsdHelper.gen_osdmap_tree_nodes(osdmap_tree_node_ids)}
            raise NotImplementedError()

        def mgr_get_counter_replacement(svc_type, _, path):
            if svc_type == 'osd':
                return {path: OsdHelper.gen_mgr_get_counter()}
            raise NotImplementedError()

        with mock.patch.object(Osd, 'get_osd_map', return_value=OsdHelper.gen_osdmap(osdmap_ids)):
            with mock.patch.object(mgr, 'get', side_effect=mgr_get_replacement):
                with mock.patch.object(mgr, 'get_counter', side_effect=mgr_get_counter_replacement):
                    with mock.patch.object(mgr, 'get_latest', return_value=1146609664):
                        with mock.patch.object(Osd, 'get_removing_osds', return_value=[]):
                            yield

    def _get_drive_group_data(self, service_id='all_hdd', host_pattern_k='host_pattern',
                              host_pattern_v='*'):
        return {
            'method': 'drive_groups',
            'data': [
                {
                    'service_type': 'osd',
                    'service_id': service_id,
                    'data_devices': {
                        'rotational': True
                    },
                    host_pattern_k: host_pattern_v
                }
            ],
            'tracking_id': 'all_hdd, b_ssd'
        }

    def test_osd_list_aggregation(self):
        """
        This test emulates the state of a cluster where an OSD has only been
        removed (with e.g. `ceph osd rm`), but it hasn't been removed from the
        CRUSH map.  Ceph reports a health warning alongside a `1 osds exist in
        the crush map but not in the osdmap` warning in such a case.
        """
        osds_actual = [0, 1]
        osds_leftover = [0, 1, 2]
        with self._mock_osd_list(osd_stat_ids=osds_actual, osdmap_tree_node_ids=osds_leftover,
                                 osdmap_ids=osds_actual):
            self._get('/api/osd')
            self.assertEqual(len(self.json_body()), 2, 'It should display two OSDs without failure')
            self.assertStatus(200)

    @mock.patch('dashboard.controllers.osd.CephService')
    def test_osd_create_bare(self, ceph_service):
        ceph_service.send_command.return_value = '5'
        sample_data = {
            'uuid': 'f860ca2e-757d-48ce-b74a-87052cad563f',
            'svc_id': 5
        }

        data = {
            'method': 'bare',
            'data': sample_data,
            'tracking_id': 'bare-5'
        }
        self._task_post('/api/osd', data)
        self.assertStatus(201)
        ceph_service.send_command.assert_called()

    @mock.patch('dashboard.controllers.orchestrator.OrchClient.instance')
    def test_osd_create_with_drive_groups(self, instance):
        # without orchestrator service
        fake_client = mock.Mock()
        instance.return_value = fake_client

        # Valid DriveGroup
        data = self._get_drive_group_data()

        # Without orchestrator service
        fake_client.available.return_value = False
        self._task_post('/api/osd', data)
        self.assertStatus(503)

        # With orchestrator service
        fake_client.available.return_value = True
        fake_client.get_missing_features.return_value = []
        self._task_post('/api/osd', data)
        self.assertStatus(201)
        dg_specs = [DriveGroupSpec(placement=PlacementSpec(host_pattern='*'),
                                   service_id='all_hdd',
                                   service_type='osd',
                                   data_devices=DeviceSelection(rotational=True))]
        fake_client.osds.create.assert_called_with(dg_specs)

    @mock.patch('dashboard.controllers.orchestrator.OrchClient.instance')
    def test_osd_create_with_invalid_drive_groups(self, instance):
        # without orchestrator service
        fake_client = mock.Mock()
        instance.return_value = fake_client
        fake_client.get_missing_features.return_value = []

        # Invalid DriveGroup
        data = self._get_drive_group_data('invalid_dg', 'host_pattern_wrong', 'unknown')
        self._task_post('/api/osd', data)
        self.assertStatus(400)

    @mock.patch('dashboard.controllers.osd.CephService')
    def test_osd_mark_all_actions(self, instance):
        fake_client = mock.Mock()
        instance.return_value = fake_client
        action_list = ['OUT', 'IN', 'DOWN']
        for action in action_list:
            data = {'action': action}
            self._task_put('/api/osd/1/mark', data)
            self.assertStatus(200)