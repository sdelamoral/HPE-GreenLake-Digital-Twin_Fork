"""
Generate HTML report from JSON validation results
"""
import json
import sys
from pathlib import Path
from datetime import datetime

def generate_html_report(json_path):
    """Convert JSON validation report to HTML"""
    
    with open(json_path, 'r') as f:
        report = json.load(f)
    
    summary = report['summary']
    results = report['results']
    timestamp = report['execution_timestamp']
    
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Data Quality Report - Emergency Vehicles Digital Twin</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            max-width: 1200px;
            margin: 40px auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .header {{
            background: white;
            padding: 30px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            margin: 0 0 10px 0;
            color: #333;
        }}
        .timestamp {{
            color: #666;
            font-size: 14px;
        }}
        .summary {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .metric {{
            display: inline-block;
            margin-right: 40px;
        }}
        .metric-label {{
            font-size: 12px;
            color: #666;
            text-transform: uppercase;
        }}
        .metric-value {{
            font-size: 32px;
            font-weight: bold;
            color: #333;
        }}
        .pass-rate {{
            color: {'#2ecc71' if summary['pass_rate'] >= 95 else '#e74c3c'};
        }}
        .rule-section {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 15px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .rule-header {{
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 15px;
            color: #333;
        }}
        .check {{
            padding: 12px;
            margin-bottom: 8px;
            border-radius: 4px;
            border-left: 4px solid;
        }}
        .check-pass {{
            background: #d4edda;
            border-color: #28a745;
        }}
        .check-fail {{
            background: #f8d7da;
            border-color: #dc3545;
        }}
        .check-name {{
            font-weight: 600;
            margin-bottom: 4px;
        }}
        .check-message {{
            font-size: 14px;
            color: #666;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
            margin-left: 10px;
        }}
        .badge-pass {{
            background: #28a745;
            color: white;
        }}
        .badge-fail {{
            background: #dc3545;
            color: white;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Data Quality Validation Report</h1>
        <div class="timestamp">Emergency Vehicles Digital Twin • {timestamp}</div>
    </div>
    
    <div class="summary">
        <div class="metric">
            <div class="metric-label">Total Checks</div>
            <div class="metric-value">{summary['total_checks']}</div>
        </div>
        <div class="metric">
            <div class="metric-label">Passed</div>
            <div class="metric-value" style="color: #2ecc71">{summary['passed']}</div>
        </div>
        <div class="metric">
            <div class="metric-label">Failed</div>
            <div class="metric-value" style="color: #e74c3c">{summary['failed']}</div>
        </div>
        <div class="metric">
            <div class="metric-label">Pass Rate</div>
            <div class="metric-value pass-rate">{summary['pass_rate']}%</div>
        </div>
    </div>
"""
    
    for rule_name, rule_results in results.items():
        html += f"""
    <div class="rule-section">
        <div class="rule-header">{rule_name}</div>
"""
        
        for check_name, check_result in rule_results.items():
            passed = check_result['passed']
            css_class = 'check-pass' if passed else 'check-fail'
            badge_class = 'badge-pass' if passed else 'badge-fail'
            badge_text = 'PASS' if passed else 'FAIL'
            
            html += f"""
        <div class="check {css_class}">
            <div class="check-name">
                {check_name}
                <span class="badge {badge_class}">{badge_text}</span>
            </div>
            <div class="check-message">{check_result['message']}</div>
        </div>
"""
        
        html += """
    </div>
"""
    
    html += """
</body>
</html>
"""
    
    # Save HTML report
    html_path = json_path.parent / json_path.name.replace('.json', '.html')
    with open(html_path, 'w') as f:
        f.write(html)
    
    print(f"HTML report generated: {html_path}")
    return html_path

if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Find most recent JSON report
        log_dir = Path("data_quality/logs")
        json_files = list(log_dir.glob("validation_report_*.json"))
        if not json_files:
            print("No validation reports found")
            sys.exit(1)
        
        json_path = max(json_files, key=lambda p: p.stat().st_mtime)
        print(f"Using most recent report: {json_path}")
    else:
        json_path = Path(sys.argv[1])
    
    generate_html_report(json_path)