"""
基础功能测试
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestConfigLoader:
    def test_load_models(self):
        from src.utils.config_loader import ConfigLoader
        base = os.path.join(os.path.dirname(__file__), '..', 'config')
        c = ConfigLoader(base)
        models = c.get_all_models()
        assert len(models) > 0

    def test_tracks(self):
        from src.utils.config_loader import ConfigLoader
        base = os.path.join(os.path.dirname(__file__), '..', 'config')
        c = ConfigLoader(base)
        tracks = c.get_all_tracks_include_industry()
        assert 'text' in tracks
        assert 'industry' in tracks
        assert len(tracks) == 6

    def test_model_by_track(self):
        from src.utils.config_loader import ConfigLoader
        base = os.path.join(os.path.dirname(__file__), '..', 'config')
        c = ConfigLoader(base)
        text_models = c.get_models_by_track('text')
        assert len(text_models) == 3


class TestGenerator:
    def test_text_cases(self):
        from src.engine.generator import TestCaseGenerator
        g = TestCaseGenerator()
        cases = g.generate_text_cases('test-model')
        assert len(cases) > 0
        assert cases[0].track == 'text'

    def test_image_cases(self):
        from src.engine.generator import TestCaseGenerator
        g = TestCaseGenerator()
        cases = g.generate_image_cases('test-model')
        assert len(cases) > 0
        assert cases[0].track == 'image'

    def test_industry_cases(self):
        from src.engine.generator import TestCaseGenerator
        g = TestCaseGenerator()
        cases = g.generate_industry_cases('test-model')
        assert len(cases) > 0
        categories = {c.category for c in cases}
        assert 'qa' in categories
        assert 'compliance' in categories

    def test_audio_cases(self):
        from src.engine.generator import TestCaseGenerator
        g = TestCaseGenerator()
        cases = g._gen_audio_all('test-model')
        assert len(cases) > 0
        assert any(c.sub_track == 'tts' for c in cases)
        assert any(c.sub_track == 'asr' for c in cases)


class TestMetrics:
    def test_request_metric(self):
        from src.utils.metrics import RequestMetric
        m = RequestMetric(test_case_id='tc1', model_id='m1')
        m.request_start = 1000.0
        m.first_token_time = 1000.5
        m.request_end = 1001.0
        m.output_tokens = 100
        assert round(m.ttft, 2) == 0.5
        assert round(m.total_duration, 2) == 1.0
        assert round(m.speed, 2) == 200.0

    def test_track_metrics_p1(self):
        from src.utils.metrics import TrackMetrics, RequestMetric
        metrics = [
            RequestMetric(test_case_id=f'tc{i}', model_id='m1',
                          input_tokens=100, output_tokens=50)
            for i in range(10)
        ]
        tm = TrackMetrics(track='text', model_id='m1', metrics=metrics)
        assert tm.total_requests == 10
        assert tm.success_rate == 0.0  # pending status


class TestReportGenerator:
    def test_generate_html(self):
        import tempfile
        from src.utils.report_generator import ReportGenerator
        with tempfile.TemporaryDirectory() as tmpdir:
            rg = ReportGenerator(tmpdir)
            path = rg.generate_html_report({}, run_id='test-001')
            assert os.path.exists(path)
            with open(path) as f:
                content = f.read()
            assert '北京移动' in content
