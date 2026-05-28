#!/bin/bash
# 快速测试：只跑文本赛道的基本功能
set -e
cd "$(dirname "$0")/.."

echo "🧪 快速测试..."

# 1. 验证配置加载
python3 -c "
from src.utils.config_loader import ConfigLoader
c = ConfigLoader()
print(f'模型数量: {c.get_models_summary()[\"total\"]}')
print(f'赛道: {\", \".join(c.get_all_tracks_include_industry())}')
"

# 2. 验证用例生成
python3 -c "
from src.engine.generator import TestCaseGenerator
g = TestCaseGenerator()
cases = g.generate_cases_for_model('test-model', 'text', {})
print(f'文本赛道用例数: {len(cases)}')
cases = g.generate_industry_cases('test-model')
print(f'行业赛道用例数: {len(cases)}')
"

echo "✅ 全部测试通过"
