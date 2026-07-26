import os
import tempfile
import unittest

import numpy as np
from docx import Document
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Table

from core.report_generator import ReportGenerator, _graph_interp, _tbl


ROI_NAMES = [
    'mPFC', 'PCC', 'Precuneus', 'L_Angular', 'R_Angular', 'L_mTL_HPC',
    'R_mTL_HPC', 'ACC_dACC', 'L_AI', 'R_AI', 'L_dlPFC', 'R_dlPFC',
    'L_IPL', 'R_IPL', 'L_M1', 'R_M1', 'SMA', 'V1_L', 'V1_R', 'LOC_L',
    'L_FEF', 'R_FEF', 'L_IPS', 'R_IPS', 'L_Amy', 'R_Amy', 'L_Thal',
    'R_Thal', 'L_Caudate', 'R_Caudate', 'Brainstem', 'L_Cerebellum',
    'R_Cerebellum',
]


def make_generator(output_dir):
    rng = np.random.default_rng(42)
    fc = rng.uniform(-0.15, 0.65, (len(ROI_NAMES), len(ROI_NAMES)))
    fc = (fc + fc.T) / 2
    np.fill_diagonal(fc, 0)

    network_rois = {
        'DMN': ROI_NAMES[0:7], 'SN': ROI_NAMES[7:10],
        'ECN': ROI_NAMES[10:14], 'SMN': ROI_NAMES[14:17],
        'VIS': ROI_NAMES[17:20], 'DAN': ROI_NAMES[20:24],
        'LMB': ROI_NAMES[24:28], 'SUB': ROI_NAMES[28:33],
    }
    network_stats = {
        key: {'rois': rois, 'mean_FC': 0.25 + 0.02 * idx, 'std_FC': 0.08}
        for idx, (key, rois) in enumerate(network_rois.items())
    }
    per_node = {
        name: {
            'degree': 12 + idx % 8,
            'betweenness_centrality': 0.01 * (idx % 10),
            'clustering_coefficient': 0.45 + 0.01 * (idx % 20),
            'eigenvector_centrality': 0.10 + 0.01 * (idx % 15),
            'participation_coefficient': 0.30 + 0.01 * (idx % 25),
        }
        for idx, name in enumerate(ROI_NAMES)
    }
    scan_params = {
        'subject_id': 'QA_GE0603', 'age': '035Y', 'sex': 'M',
        'institution': 'QA Lab', 'scanner': 'QA Scanner',
        'scan_date': '2026-07-26', 'TR': 2.0, 'TE': 30,
        'voxel_size': '3×3×3', 'slice_timing_available': True,
    }
    qc = {
        'QC_score': 82, 'QC_stars': '★★★★', 'n_timepoints': 240,
        'total_duration_min': 8.0, 'tSNR_median': 61.2,
        'DVARS_pct_median': 2.4, 'FD_proxy_pct_median': 0.22,
        'n_bad_TPs': 8, 'pct_bad_TPs': 3.3,
    }
    graph = {
        'threshold_r': 0.2, 'n_nodes': 33, 'n_edges': 210, 'density': 0.398,
        'mean_degree': 15.3, 'avg_clustering': 0.61,
        'global_efficiency': 0.603, 'local_efficiency': 0.86,
        'char_path_length': 2.1, 'small_world_sigma': 1.35,
        'modularity': 0.34, 'n_communities': 5,
        'hub_regions': ['PCC', 'L_AI', 'L_Caudate'], 'per_node': per_node,
    }
    dynamic = {
        'n_windows': 42, 'n_transitions': 6, 'window_size_TPs': 44,
        'window_size_s': 88, 'step_TPs': 4,
        'state_occupancy': {'State_1': 0.57, 'State_2': 0.43},
        'dwell_times_s': {'State_1': 260, 'State_2': 190},
        'scan_duration_min': 8.0,
    }
    results = {
        'scan_params': scan_params, 'qc_metrics': qc, 'graph': graph,
        'dynamic': dynamic, 'alff': {'alff_mean': 0.0, 'falff_mean': 0.0},
        'reho': {'reho_mean': 0.0}, 'multimodal': {},
    }
    generator = ReportGenerator(results, output_dir, scan_params=scan_params)
    generator.qc = qc
    generator.gm = graph
    generator.ns = network_stats
    generator.dfc = dynamic
    generator.roi_names = ROI_NAMES
    generator.FC = fc
    generator.fp = {'dmn_strength': 0.31}
    return generator


class ReportGeneratorRegressionTests(unittest.TestCase):
    def test_ge_feature_uses_the_chapter_8_reference_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            feature_zh, _, matched = make_generator(tmp).disease_similarity()['ADHD']['features'][1]
        self.assertFalse(matched)
        self.assertEqual(
            feature_zh,
            '全局效率GE=0.603，位于项目参考区间0.5–0.8，不属于偏低',
        )
        self.assertNotIn('0.603<0.30', feature_zh)
        self.assertEqual(_graph_interp('global_efficiency', 0.603), '正常范围')

    def test_low_ge_matches_the_same_project_lower_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            generator = make_generator(tmp)
            generator.gm['global_efficiency'] = 0.499
            feature_zh, _, matched = generator.disease_similarity()['ADHD']['features'][1]
        self.assertTrue(matched)
        self.assertEqual(
            feature_zh,
            '全局效率GE=0.499，低于项目参考下限0.50，属于偏低',
        )
        self.assertEqual(_graph_interp('global_efficiency', 0.499), '偏低')

    def test_clustering_high_rule_uses_the_chapter_8_upper_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            generator = make_generator(tmp)
            feature_zh, _, matched = generator.disease_similarity()['ASD']['features'][0]
        self.assertFalse(matched)
        self.assertEqual(
            feature_zh,
            '局部聚类CC=0.610，位于项目参考区间0.5–0.8，不属于偏高',
        )

    def test_adhd_reports_rule_count_not_a_similarity_level(self):
        with tempfile.TemporaryDirectory() as tmp:
            generator = make_generator(tmp)
            generator.ns['DAN']['mean_FC'] = 0.054
            adhd = generator.disease_similarity()['ADHD']
        self.assertEqual(adhd['n_hit'], 2)
        self.assertEqual(adhd['n_tot'], 3)
        self.assertEqual(adhd['level_zh'], '2/3项规则命中')
        self.assertNotIn('中度', adhd['level_zh'])
        self.assertFalse(adhd['features'][1][2])

    def test_pdf_table_cells_wrap_and_fit_a4_body(self):
        table = _tbl([
            ['列一', '列二'],
            ['很长的中文文本' * 20, '另一段很长的中文文本' * 20],
        ], cw=[12 * cm, 12 * cm])
        self.assertIsInstance(table, Table)
        self.assertLessEqual(sum(table._colWidths), 17 * cm + 0.01)
        self.assertIsInstance(table._cellvalues[1][0], Paragraph)

    def test_word_uses_the_complete_pdf_story(self):
        with tempfile.TemporaryDirectory() as tmp:
            generator = make_generator(tmp)
            expected_headings = [
                '一、扫描参数与数据概览', '二、数据预处理流程',
                '三、数据质量控制（QC）', '四、ROI定义与静息态脑网络分析',
                '五、默认模式网络（DMN）专项分析', '六、全脑功能连接分析',
                '七、局部脑活动分析（ALFF / fALFF / ReHo）',
                '八、脑功能网络图论分析', '九、动态功能连接分析',
                '十、神经精神疾病脑网络文献对照分析',
                '十一、神经科学讨论', '十二、方法学说明与可重复性',
                '附录：全部 ROI 图论指标',
            ]
            story_text = '\n'.join(
                flow.getPlainText()
                for flow in generator._zh_story()
                if isinstance(flow, Paragraph)
            )
            self.assertIn('GE<0.50记为偏低', story_text)
            docx_path = generator.generate_word_report('zh')
            self.assertTrue(os.path.exists(docx_path))
            document = Document(docx_path)
            word_text = '\n'.join([
                *(p.text for p in document.paragraphs),
                *(
                    cell.text
                    for table in document.tables
                    for row in table.rows
                    for cell in row.cells
                ),
            ])
            for heading in expected_headings:
                self.assertIn(heading, story_text)
                self.assertIn(heading, word_text)
            self.assertIn('GE<0.50记为偏低', word_text)
            self.assertIn(
                '全局效率GE=0.603，位于项目参考区间0.5–0.8，不属于偏低',
                word_text,
            )
            self.assertNotIn('0.603<0.30', word_text)


if __name__ == '__main__':
    unittest.main()
