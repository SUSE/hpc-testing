#!/usr/bin/env python3
import glob
import csv
import json
import os
import subprocess
import re

def parse_csvs(root_dir):
    data = {
        "testnames": set(),
        "configs": set(),
        "sizes": [], # We will extract sizes from the first file we see
        "units": {}, # Extracted from the 2nd column
        "results": {} # Structure: { testname: { config: [results...] } }
    }
    
    csv_files = glob.glob(os.path.join(root_dir, 'results', '*', '*.csv'))
    
    for filepath in csv_files:
        # Extract config from path: results/<host>/<flavour>.csv
        parts = filepath.split(os.sep)
        if len(parts) >= 3:
            host = parts[-2]
            flavour = parts[-1].replace('.csv', '')
            config = f"{host}/{flavour}"
            data["configs"].add(config)
            
            with open(filepath, 'r') as f:
                reader = csv.reader(f)
                header = next(reader, None)
                if not header:
                    continue
                
                # Sizes are from column 2 onwards. Sanitize alphanumeric units out (e.g. 2B => 2)
                if not data["sizes"]:
                    try:
                        szs = []
                        for x in header[2:]:
                            m = re.search(r'\d+', x)
                            if m:
                                szs.append(int(m.group()))
                        
                        if len(szs) > 0:
                            data["sizes"] = szs
                    except Exception:
                        continue
                
                for row in reader:
                    if len(row) < 2:
                        continue
                    testname = row[0]
                    if not testname:
                        continue
                        
                    data["testnames"].add(testname)
                    
                    if testname not in data["results"]:
                        data["results"][testname] = {}
                        if len(row) > 1:
                            data["units"][testname] = row[1]
                        
                    # Extract values, mapping empty strings to None
                    values = []
                    for val in row[2:]:
                        if val.strip() == '':
                            values.append(None)
                        else:
                            try:
                                values.append(float(val))
                            except ValueError:
                                values.append(None)
                                
                    data["results"][testname][config] = values

    # Convert sets to sorted lists for JSON serialization
    data["testnames"] = sorted(list(data["testnames"]))
    data["configs"] = sorted(list(data["configs"]))
    return data

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hpc-Testing Results Dashboard</title>
    <!-- Modern Fonts -->
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <!-- Plotly via CDN -->
    <script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
    <style>
        :root {
            --bg-color: #0f172a;
            --panel-bg: rgba(30, 41, 59, 0.7);
            --border-color: rgba(255, 255, 255, 0.1);
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --accent: #3b82f6;
            --accent-hover: #60a5fa;
            --shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -1px rgba(0, 0, 0, 0.2);
            --radius: 12px;
        }

        body {
            margin: 0;
            padding: 0;
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #020617 0%, #0f172a 100%);
            color: var(--text-main);
            min-height: 100vh;
        }

        .container {
            display: flex;
            height: 100vh;
            overflow: hidden;
            position: relative;
        }

        .mode-btn {
            background: transparent;
            border: 1px solid transparent;
            color: var(--text-muted);
            padding: 4px 8px;
            font-size: 0.85rem;
            font-weight: 600;
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .mode-btn.active {
            background: rgba(59, 130, 246, 0.1);
            border-color: rgba(59, 130, 246, 0.3);
            color: var(--accent);
        }

        .mode-btn:hover:not(.active) {
            background: rgba(255, 255, 255, 0.05);
            color: var(--text-main);
        }

        /* Sidebar Styling */
        .sidebar {
            width: 280px;
            flex-shrink: 0;
            background: var(--panel-bg);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border-right: 1px solid var(--border-color);
            padding: 12px;
            display: flex;
            flex-direction: column;
            gap: 12px;
            overflow-y: auto;
            box-shadow: var(--shadow);
            z-index: 10;
            transition: margin-left 0.3s ease;
        }
        
        .sidebar.collapsed {
            margin-left: -280px;
        }

        .control-group {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }

        .control-group label.group-title {
            font-size: 0.8rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            display: block;
        }

        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
        }

        .stat-card {
            background: rgba(30, 41, 59, 0.7);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 16px;
            display: flex;
            flex-direction: column;
            gap: 4px;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
        }

        .stat-card .stat-title {
            font-size: 0.8rem;
            color: var(--text-muted);
            font-weight: 600;
            text-transform: uppercase;
        }

        .stat-card .stat-value {
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--text-main);
        }

        select {
            background-color: rgba(15, 23, 42, 0.8);
            background-image: url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3e%3cpolyline points='6 9 12 15 18 9'%3e%3c/polyline%3e%3c/svg%3e");
            background-repeat: no-repeat;
            background-position: right 8px center;
            background-size: 12px;
            color: var(--text-main);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            padding: 4px 24px 4px 8px;
            font-family: inherit;
            font-size: 0.8rem;
            width: 100%;
            outline: none;
            transition: all 0.2s ease;
            appearance: none;
            cursor: pointer;
        }

        select:focus {
            border-color: var(--accent);
            box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.3);
        }

        button.nav-btn {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border-color);
            color: var(--text-main);
            padding: 2px 4px;
            border-radius: 4px;
            font-family: inherit;
            font-size: 0.9rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
            display: grid;
            place-content: center;
        }

        button.nav-btn:hover {
            background: rgba(255, 255, 255, 0.1);
            border-color: rgba(255, 255, 255, 0.2);
        }

        .nav-icon {
            width: 12px;
            height: 12px;
            stroke: currentColor;
            stroke-width: 2;
        }

        .checkbox-container {
            display: flex;
            flex-direction: column;
            gap: 2px;
            flex: 1;
            overflow-y: auto;
            padding-right: 4px;
            scrollbar-width: thin;
            scrollbar-color: var(--border-color) transparent;
        }
        
        .checkbox-container::-webkit-scrollbar {
            width: 6px;
        }
        .checkbox-container::-webkit-scrollbar-track {
            background: transparent;
        }
        .checkbox-container::-webkit-scrollbar-thumb {
            background-color: var(--border-color);
            border-radius: 10px;
        }

        .checkbox-label {
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 0.8rem;
            cursor: pointer;
            padding: 2px 4px;
            border-radius: 4px;
            transition: background 0.2s;
        }

        .checkbox-label:hover, .group-header:hover {
            background: rgba(255, 255, 255, 0.05);
        }

        input[type="checkbox"] {
            appearance: none;
            background-color: rgba(255,255,255,0.1);
            margin: 0;
            font: inherit;
            color: currentColor;
            width: 14px;
            height: 14px;
            border: 1px solid var(--border-color);
            border-radius: 3px;
            display: grid;
            place-content: center;
            cursor: pointer;
            transition: all 0.2s;
        }

        input[type="checkbox"]::before {
            content: "";
            width: 8px;
            height: 8px;
            transform: scale(0);
            transition: 120ms transform ease-in-out;
            box-shadow: inset 1em 1em white;
            background-color: white;
            border-radius: 2px;
            transform-origin: center;
            clip-path: polygon(14% 44%, 0 65%, 50% 100%, 100% 16%, 80% 0%, 43% 62%);
        }
        
        input[type="checkbox"]:indeterminate::before {
            clip-path: polygon(0 40%, 100% 40%, 100% 60%, 0 60%);
            transform: scale(1);
        }

        input[type="checkbox"]:checked {
            background-color: var(--accent);
            border-color: var(--accent);
        }

        input[type="checkbox"]:checked::before {
            transform: scale(1);
        }

        .config-group {
            margin-bottom: 4px;
        }

        .group-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
            font-size: 0.85rem;
            font-weight: 600;
            cursor: pointer;
            padding: 4px 8px;
            border-radius: 4px;
            background: rgba(255, 255, 255, 0.05);
            transition: background 0.2s;
            color: var(--accent-hover);
        }

        .group-header:hover {
            background: rgba(255, 255, 255, 0.1);
        }

        .group-children {
            padding-left: 8px;
            margin-top: 2px;
            display: flex;
            flex-direction: column;
            gap: 2px;
        }

        /* Tabs Styling */
        .tabs {
            position: absolute;
            top: 8px;
            right: 8px;
            z-index: 20;
            display: flex;
            background: rgba(15, 23, 42, 0.9);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 3px;
            box-shadow: var(--shadow);
        }

        .tab-btn {
            background: transparent;
            border: none;
            color: var(--text-muted);
            padding: 4px 10px;
            font-size: 0.75rem;
            font-weight: 600;
            cursor: pointer;
            border-radius: 4px;
            transition: all 0.2s;
        }

        .tab-btn.active {
            color: var(--text-main);
            background: var(--accent);
            box-shadow: 0 1px 3px rgba(0,0,0,0.3);
        }

        .tab-btn:hover:not(.active) {
            color: var(--text-main);
            background: rgba(255, 255, 255, 0.05);
        }

        /* Main Content Styling */
        .main-content {
            flex: 1;
            padding: 0;
            display: flex;
            flex-direction: column;
            position: relative;
            min-width: 0;
            background: transparent;
        }

        .sidebar-toggle {
            position: absolute;
            top: 8px;
            left: -16px;
            z-index: 50;
            background: var(--panel-bg);
            border: 1px solid var(--border-color);
            color: var(--text-muted);
            width: 32px;
            height: 32px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: left 0.3s ease, background 0.2s, color 0.2s;
            box-shadow: var(--shadow);
        }
        
        .sidebar-toggle:hover {
            color: var(--text-main);
            background: rgba(255, 255, 255, 0.1);
        }
        
        .sidebar-toggle svg {
            width: 16px;
            height: 16px;
            transition: transform 0.3s ease;
        }
        
        .sidebar.collapsed ~ .main-content .sidebar-toggle {
            left: 12px;
        }

        .sidebar.collapsed ~ .main-content .sidebar-toggle svg {
            transform: rotate(180deg);
        }

        .tab-pane {
            display: none;
            flex: 1;
            padding: 0;
            padding-top: 40px; /* space for absolute tabs */
            position: relative;
            overflow: hidden; /* Handled by internal wrappers for smooth sticky */
        }

        .tab-pane.active {
            display: flex;
            flex-direction: column;
        }
        
        /* Table Wrapper for Perfect Scrolling */
        .table-wrapper {
            flex: 1;
            overflow: auto;
            border-radius: 4px;
        }
        
        #plot {
            width: 100%;
            height: 100%;
            flex: 1;
        }

        .empty-state {
            position: absolute;
            inset: 0;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1rem;
            color: var(--text-muted);
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.3s;
        }

        .empty-state.active {
            opacity: 1;
        }

        /* Table Styling */
        .data-table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            font-size: 0.8rem;
            text-align: right;
            margin: 0;
        }
        
        .data-table th, .data-table td {
            padding: 6px 12px;
            border-bottom: 1px solid var(--border-color);
            white-space: nowrap;
        }
        
        .data-table th {
            color: var(--text-main);
            font-weight: 600;
            background: rgba(30, 41, 59, 0.95);
            position: sticky;
            top: 0;
            z-index: 2;
        }
        
        .data-table td {
            color: #cbd5e1;
            font-family: monospace;
        }

        .data-table tbody tr:hover td, .data-table tbody tr:hover th {
            background: rgba(255, 255, 255, 0.05);
        }
        
        .data-table th.col-fixed, .data-table td.col-fixed {
            text-align: left;
            position: sticky;
            left: 0;
            background: rgba(30, 41, 59, 1);
            z-index: 1;
            border-right: 1px solid var(--border-color);
        }
        
        .data-table th.col-fixed {
            z-index: 3;
            color: var(--accent);
        }

    </style>
</head>
<body>
    <div class="container">
        <!-- Sidebar Controls -->
        <div class="sidebar">
            
            <!-- Global Mode Toggles -->
            <div style="display: flex; gap: 4px; padding-bottom: 8px; border-bottom: 1px solid var(--border-color);">
                <button id="mode-explorer" class="mode-btn active" style="flex: 1; justify-content: center;">📊 Explorer</button>
                <button id="mode-sweep" class="mode-btn" style="flex: 1; justify-content: center;">🔍 Sweep</button>
            </div>

            <!-- EXPLORER SIDEBAR -->
            <div id="sidebar-explorer" style="display: flex; flex-direction: column; flex: 1; overflow: hidden;">
                <div style="display: flex; flex-direction: column; gap: 8px; padding-bottom: 8px; border-bottom: 1px solid var(--border-color);">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="font-weight: 600; width: 60px; color: var(--text-muted); font-size: 0.8rem;">Class:</span>
                        <select id="class-select" style="flex: 1;"></select>
                    </div>
                    
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="font-weight: 600; width: 60px; color: var(--text-muted); font-size: 0.8rem;">Test:</span>
                        <div style="display: flex; gap: 4px; align-items: center; flex: 1;">
                            <button class="nav-btn" id="prev-test" title="Previous Test (Left Arrow)">
                                <svg viewBox="0 0 24 24" fill="none" class="nav-icon"><polyline points="15 18 9 12 15 6"></polyline></svg>
                            </button>
                            <select id="test-select" style="flex: 1; background-image: none; padding-right: 8px;"></select>
                            <button class="nav-btn" id="next-test" title="Next Test (Right Arrow)">
                                <svg viewBox="0 0 24 24" fill="none" class="nav-icon"><polyline points="9 18 15 12 9 6"></polyline></svg>
                            </button>
                        </div>
                    </div>
                </div>

                <div style="display: flex; flex-direction: column; gap: 8px; padding-top: 8px; padding-bottom: 8px; border-bottom: 1px solid var(--border-color);">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="font-weight: 600; width: 60px; color: var(--text-muted); font-size: 0.8rem;">Baseline:</span>
                        <input type="checkbox" id="baseline-enable" checked title="Enable Baseline Comparison">
                        <select id="baseline-select" style="flex: 1;">
                            <option value="">None</option>
                        </select>
                    </div>
                    <div style="display: flex; gap: 12px; margin-left: 68px;">
                        <label class="checkbox-label" style="padding: 0;"><input type="checkbox" id="log-x" checked> Log X</label>
                        <label class="checkbox-label" style="padding: 0;"><input type="checkbox" id="log-y"> Log Y</label>
                    </div>
                </div>

                <div class="control-group" style="flex: 1; overflow: hidden; display: flex; flex-direction: column; padding-top: 8px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2px;">
                        <label class="group-title">Configurations</label>
                        <div style="display: flex; gap: 8px; font-size: 0.75rem;">
                            <span style="color: var(--text-muted);">Group:</span>
                            <a href="#" id="toggle-groupby" style="color: var(--accent); text-decoration: none;">Host</a>
                        </div>
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                        <div style="display: flex; gap: 8px;">
                            <a href="#" id="sel-all" style="font-size: 0.75rem; color: var(--accent); text-decoration: none;">Select All</a>
                            <a href="#" id="sel-none" style="font-size: 0.75rem; color: var(--text-muted); text-decoration: none;">Clear</a>
                        </div>
                        <div style="display: flex; gap: 8px;">
                            <a href="#" id="expand-all" style="font-size: 0.75rem; color: var(--accent); text-decoration: none;">Expand All</a>
                            <a href="#" id="collapse-all" style="font-size: 0.75rem; color: var(--text-muted); text-decoration: none;">Collapse All</a>
                        </div>
                    </div>
                    <div class="checkbox-container" id="config-checkboxes">
                        <!-- Checkboxes injected by JS -->
                    </div>
                </div>
            
            </div> <!-- CLOSE sidebar-explorer -->

            <!-- REGRESSION SWEEP SIDEBAR -->
            <div id="sidebar-sweep" style="display: none; flex-direction: column; flex: 1;">
                <div class="control-group" style="padding-bottom: 8px; border-bottom: 1px solid var(--border-color); margin-bottom: 8px;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="font-weight: 600; width: 60px; color: var(--text-muted); font-size: 0.8rem;">Baseline:</span>
                        <select id="sweep-baseline-select" style="flex: 1;">
                            <option value="">None</option>
                        </select>
                    </div>
                    <div style="display: flex; align-items: center; gap: 8px; margin-top: 4px;">
                        <span style="font-weight: 600; width: 60px; color: var(--text-muted); font-size: 0.8rem;">Target:</span>
                        <select id="target-select" style="flex: 1;">
                            <option value="">None</option>
                        </select>
                    </div>
                </div>
                
                <div style="display: flex; flex-direction: column; flex: 1; overflow: hidden;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                        <label class="group-title">Sweep Environments</label>
                    </div>
                    <div style="display: flex; justify-content: flex-end; gap: 8px; margin-bottom: 6px;">
                        <a href="#" id="env-sel-all" style="font-size: 0.75rem; color: var(--accent); text-decoration: none;">Select All</a>
                        <a href="#" id="env-sel-none" style="font-size: 0.75rem; color: var(--text-muted); text-decoration: none;">Clear</a>
                    </div>
                    <div class="checkbox-container" id="env-checkboxes">
                        <!-- NavCheckboxes injected by JS -->
                    </div>
                </div>
            </div>

        </div>

        <!-- Main Graph Area -->
        <div id="main-explorer" class="main-content">
            <button id="sidebar-toggle" class="sidebar-toggle" title="Toggle Sidebar">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="15 18 9 12 15 6"></polyline>
                </svg>
            </button>
            <div id="graph-title" style="position: absolute; top: 8px; left: 48px; z-index: 20; font-size: 1.1rem; font-weight: 600; color: #f8fafc; line-height: 28px;"></div>
            <div class="tabs">
                <button class="tab-btn active" data-target="pane-graph">Graph</button>
                <button class="tab-btn" data-target="pane-table">Data Table</button>
            </div>
            
            <div id="pane-graph" class="tab-pane active">
                <div id="plot"></div>
                <div id="graph-empty" class="empty-state">No configurations selected.</div>
            </div>

            <div id="pane-table" class="tab-pane">
                <div class="table-wrapper">
                    <table class="data-table" id="data-table">
                        <!-- JS fills this dynamically -->
                    </table>
                </div>
                <div id="table-empty" class="empty-state">No configurations selected.</div>
            </div>

        </div>

        <!-- Main Sweep Area -->
        <div id="main-sweep" class="main-content" style="display: none; background: #0f172a; overflow-y: auto; padding: 24px;">
            <div style="max-width: 1400px; margin: 0 auto; width: 100%;">
                
                <div class="stats-grid" style="margin-bottom: 24px;">
                    <div class="stat-card">
                        <div class="stat-title">Points Evaluated</div>
                        <div class="stat-value" id="stat-evaluated">0</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-title">Regressions (>5%)</div>
                        <div class="stat-value" id="stat-regressions" style="color: #ef4444;">0</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-title">Mean Gain/Loss</div>
                        <div class="stat-value" id="stat-mean">0%</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-title">Variance</div>
                        <div class="stat-value" id="stat-variance">0</div>
                    </div>
                </div>

                <div class="table-wrapper" style="background: rgba(30, 41, 59, 1); padding: 0; border-radius: 8px; border: 1px solid var(--border-color); overflow: auto; max-height: calc(100vh - 200px);">
                    <table class="data-table" id="regression-table">
                        <thead id="regression-thead" style="cursor: pointer;"></thead>
                        <tbody id="regression-tbody"></tbody>
                    </table>
                    <div id="regression-empty" class="empty-state active" style="position: static; padding: 40px; text-align: center;">Select a Baseline and Target Host to sweep regressions.</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // DATA PLACEHOLDER
        // The python script will replace this string with the actual JSON payload
        const rawData = // JSON_PAYLOAD_HERE //;

        // Extract structured data
        const testNames = rawData.testnames;
        const xSizes = rawData.sizes;
        const results = rawData.results;
        const units = rawData.units || {};

        // Build Test Classes mapping dynamically
        const testClasses = {};
        
        testNames.forEach(t => {
            const availableConfigs = Object.keys(results[t] || {});
            if (availableConfigs.length > 0) {
                const parts = availableConfigs[0].split('/'); // e.g. "sle16-sp0" and "MPI-openmpi5"
                const classParts = parts.length > 1 ? parts[1].split('-') : []; // "MPI" and "openmpi5"
                const tClass = classParts.length > 0 ? classParts[0] : 'Other';
                
                if (!testClasses[tClass]) testClasses[tClass] = [];
                testClasses[tClass].push(t);
            }
        });

        const sortedClasses = Object.keys(testClasses).sort();
        let currentClass = sortedClasses.length > 0 ? sortedClasses[0] : null;
        let currentTestList = currentClass ? testClasses[currentClass] : testNames;

        // State
        let currentTestIdx = 0;
        let selectedConfigs = new Set();
        let collapsedGroups = new Set();
        let xAxisType = 'log';
        let yAxisType = 'linear';
        let groupBy = 'host'; // 'host' or 'flavour'

        // DOM Elements
        const sidebarEl = document.querySelector('.sidebar');
        const sidebarToggle = document.getElementById('sidebar-toggle');
        const classSelect = document.getElementById('class-select');
        const testSelect = document.getElementById('test-select');
        const configContainer = document.getElementById('config-checkboxes');
        const baselineSelect = document.getElementById('baseline-select');
        const sweepBaselineSelect = document.getElementById('sweep-baseline-select');
        const targetSelect = document.getElementById('target-select');
        const graphEmpty = document.getElementById('graph-empty');
        const tableEmpty = document.getElementById('table-empty');
        const plotEl = document.getElementById('plot');
        const tableEl = document.getElementById('data-table');
        const toggleGroupBtn = document.getElementById('toggle-groupby');

        const modeExplorer = document.getElementById('mode-explorer');
        const modeSweep = document.getElementById('mode-sweep');
        const sidebarExplorer = document.getElementById('sidebar-explorer');
        const sidebarSweep = document.getElementById('sidebar-sweep');
        const mainExplorer = document.getElementById('main-explorer');
        const mainSweep = document.getElementById('main-sweep');
        const sweepTableWrapper = document.querySelector('#main-sweep .table-wrapper');

        // URL State Management
        function getState() {
            const view = modeExplorer.classList.contains('active') ? 'explorer' : 'sweep';
            
            let pane = 'graph';
            document.querySelectorAll('.tab-btn').forEach(b => {
                if (b.classList.contains('active')) pane = b.dataset.target.replace('pane-', '');
            });

            const sweepEnvs = [];
            document.querySelectorAll('.env-filter-chk').forEach(chk => {
                if (chk.checked) sweepEnvs.push(chk.value);
            });

            return {
                view: view,
                class: classSelect.value || '',
                test: currentTestList ? (currentTestList[currentTestIdx] || '') : '',
                configs: Array.from(selectedConfigs).join(','),
                baseline: baselineSelect.value || '',
                baseline_enabled: document.getElementById('baseline-enable').checked,
                pane: pane,
                x_log: document.getElementById('log-x').checked,
                y_log: document.getElementById('log-y').checked,
                group_by: groupBy,
                collapsed: Array.from(collapsedGroups).join(','),
                sweep_baseline: sweepBaselineSelect.value || '',
                sweep_target: targetSelect.value || '',
                sweep_envs: sweepEnvs.join(','),
                sweep_sort: regSortCol + (regSortAsc ? '_asc' : '_desc'),
                sweep_scroll: view === 'sweep' ? (sweepTableWrapper.scrollTop || 0) : (window.currentSweepScroll || 0)
            };
        }

        function buildUrlForState(stateObj) {
            const params = new URLSearchParams();
            for (const [key, value] of Object.entries(stateObj)) {
                if (value !== "" && value !== null && value !== undefined) {
                    params.set(key, value);
                }
            }
            return "?" + params.toString();
        }

        let isRestoring = false;

        function updateURL(push = false) {
            if (isRestoring) return;
            const state = getState();
            const url = buildUrlForState(state);
            if (push) {
                history.pushState(null, '', url);
            } else {
                history.replaceState(null, '', url);
            }
        }

        function restoreStateFromURL() {
            const params = new URLSearchParams(window.location.search);
            if (!params.toString()) return;

            isRestoring = true;

            const view = params.get('view') || 'explorer';
            if (view === 'sweep') {
                modeSweep.classList.add('active');
                modeExplorer.classList.remove('active');
                sidebarSweep.style.display = 'flex';
                sidebarExplorer.style.display = 'none';
                mainSweep.style.display = 'flex';
                mainExplorer.style.display = 'none';
            } else {
                modeExplorer.classList.add('active');
                modeSweep.classList.remove('active');
                sidebarExplorer.style.display = 'flex';
                sidebarSweep.style.display = 'none';
                mainExplorer.style.display = 'flex';
                mainSweep.style.display = 'none';
            }

            const pane = params.get('pane') || 'graph';
            document.querySelectorAll('.tab-btn').forEach(b => {
                b.classList.remove('active');
                if (b.dataset.target === 'pane-' + pane) {
                    b.classList.add('active');
                }
            });
            document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
            const targetPane = document.getElementById('pane-' + pane);
            if (targetPane) targetPane.classList.add('active');

            const cls = params.get('class');
            if (cls && testClasses[cls]) {
                classSelect.value = cls;
                currentClass = cls;
                currentTestList = testClasses[cls];
                updateTestDropdown();
            }
            const test = params.get('test');
            if (test) {
                const tIdx = currentTestList.indexOf(test);
                if (tIdx > -1) {
                    currentTestIdx = tIdx;
                    testSelect.value = tIdx;
                }
            }

            const baseline = params.get('baseline');
            if (baseline !== null) {
                baselineSelect.value = baseline;
            }
            const baselineEnabled = params.get('baseline_enabled');
            if (baselineEnabled !== null) {
                document.getElementById('baseline-enable').checked = baselineEnabled === 'true';
            }

            const configs = params.get('configs');
            if (configs !== null) {
                selectedConfigs.clear();
                if (configs) {
                    configs.split(',').forEach(c => selectedConfigs.add(c));
                }
            }

            const xLog = params.has('x_log');
            const yLog = params.has('y_log');
            document.getElementById('log-x').checked = xLog;
            xAxisType = xLog ? 'log' : 'linear';
            document.getElementById('log-y').checked = yLog;
            yAxisType = yLog ? 'log' : 'linear';

            const gb = params.get('group_by');
            if (gb === 'host' || gb === 'flavour') {
                groupBy = gb;
                toggleGroupBtn.textContent = groupBy === 'host' ? 'Host' : 'Flavour';
            }

            const collapsed = params.get('collapsed');
            collapsedGroups.clear();
            if (collapsed) {
                collapsed.split(',').forEach(g => collapsedGroups.add(g));
            }

            const sBaseline = params.get('sweep_baseline');
            if (sBaseline !== null) sweepBaselineSelect.value = sBaseline;
            const sTarget = params.get('sweep_target');
            if (sTarget !== null) targetSelect.value = sTarget;

            const sEnvsStr = params.get('sweep_envs');
            if (sEnvsStr !== null) {
                const sEnvs = sEnvsStr ? sEnvsStr.split(',') : [];
                document.querySelectorAll('.env-filter-chk').forEach(chk => {
                    chk.checked = sEnvs.includes(chk.value);
                });
            }

            const sSort = params.get('sweep_sort');
            if (sSort) {
                if (sSort.endsWith('_asc')) {
                    regSortAsc = true;
                    regSortCol = sSort.replace('_asc', '');
                } else if (sSort.endsWith('_desc')) {
                    regSortAsc = false;
                    regSortCol = sSort.replace('_desc', '');
                }
            }

            renderConfigTree();
            updateGraph();
            if (view === 'sweep') runRegressionSweep();
            
            setTimeout(() => { Plotly.Plots.resize(plotEl); }, 50);

            const sScroll = params.get('sweep_scroll');
            if (sScroll) {
                window.currentSweepScroll = parseInt(sScroll);
                setTimeout(() => {
                    sweepTableWrapper.scrollTop = parseInt(sScroll);
                }, 100);
            }

            isRestoring = false;
        }

        // All active configs to collect hosts and envs
        const allConfigsSet = new Set();
        Object.values(results).forEach(cfgObj => {
            Object.keys(cfgObj).forEach(c => allConfigsSet.add(c));
        });
        const allConfigs = Array.from(allConfigsSet).sort();

        function init() {
            // Mode Toggle Logic
            modeExplorer.addEventListener('click', () => {
                updateURL(true);
                modeExplorer.classList.add('active');
                modeSweep.classList.remove('active');
                sidebarExplorer.style.display = 'flex';
                sidebarSweep.style.display = 'none';
                mainExplorer.style.display = 'flex';
                mainSweep.style.display = 'none';
                setTimeout(() => { Plotly.Plots.resize(plotEl); }, 50);
            });

            modeSweep.addEventListener('click', () => {
                updateURL(true);
                modeSweep.classList.add('active');
                modeExplorer.classList.remove('active');
                sidebarSweep.style.display = 'flex';
                sidebarExplorer.style.display = 'none';
                mainSweep.style.display = 'flex';
                mainExplorer.style.display = 'none';
                runRegressionSweep();
                if (window.currentSweepScroll) {
                    setTimeout(() => {
                        sweepTableWrapper.scrollTop = window.currentSweepScroll;
                    }, 100);
                }
            });

            // Sidebar toggle logic
            sidebarToggle.addEventListener('click', () => {
                sidebarEl.classList.toggle('collapsed');
                setTimeout(() => {
                    Plotly.Plots.resize(plotEl);
                }, 300); // Trigger resize after animation
            });

            // Populate Baselines and Target
            const allHostsSet = new Set();
            allConfigs.forEach(c => allHostsSet.add(c.split('/')[0]));
            Array.from(allHostsSet).sort().forEach(d => {
                const opt1 = document.createElement('option');
                opt1.value = d;
                opt1.textContent = d;
                baselineSelect.appendChild(opt1);

                const opt2 = document.createElement('option');
                opt2.value = d;
                opt2.textContent = d;
                sweepBaselineSelect.appendChild(opt2);

                const opt3 = document.createElement('option');
                opt3.value = d;
                opt3.textContent = d;
                targetSelect.appendChild(opt3);
            });

            baselineSelect.addEventListener('change', (e) => {
                updateURL();
                sweepBaselineSelect.value = e.target.value;
                updateGraph();
                if (modeSweep.classList.contains('active')) runRegressionSweep();
            });
            document.getElementById('baseline-enable').addEventListener('change', () => {
                updateURL();
                updateGraph();
            });
            sweepBaselineSelect.addEventListener('change', (e) => {
                updateURL();
                baselineSelect.value = e.target.value;
                if (modeSweep.classList.contains('active')) runRegressionSweep();
            });
            targetSelect.addEventListener('change', () => {
                updateURL();
                if (modeSweep.classList.contains('active')) runRegressionSweep();
            });

            // Populate Flavour Filter Checkboxes for Sweep Mode
            const allEnvsSet = new Set();
            allConfigs.forEach(c => allEnvsSet.add(c.split('/')[1]));
            
            const envCheckboxes = document.getElementById('env-checkboxes');
            Array.from(allEnvsSet).sort().forEach(env => {
                const lbl = document.createElement('label');
                lbl.className = 'checkbox-label';
                const chk = document.createElement('input');
                chk.type = 'checkbox';
                chk.className = 'env-filter-chk';
                chk.value = env;
                chk.checked = true; // default all on
                chk.addEventListener('change', () => {
                    if (modeSweep.classList.contains('active')) runRegressionSweep();
                    updateURL();
                });
                lbl.appendChild(chk);
                lbl.appendChild(document.createTextNode(' ' + env));
                envCheckboxes.appendChild(lbl);
            });

            document.getElementById('env-sel-all').addEventListener('click', (e) => {
                e.preventDefault();
                document.querySelectorAll('.env-filter-chk').forEach(c => c.checked = true);
                if (modeSweep.classList.contains('active')) runRegressionSweep();
                updateURL();
            });
            
            document.getElementById('env-sel-none').addEventListener('click', (e) => {
                e.preventDefault();
                document.querySelectorAll('.env-filter-chk').forEach(c => c.checked = false);
                if (modeSweep.classList.contains('active')) runRegressionSweep();
                updateURL();
            });

            // Tab switching logic
            document.querySelectorAll('.tab-btn').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                    e.target.classList.add('active');
                    
                    document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
                    document.getElementById(e.target.dataset.target).classList.add('active');
                    updateURL();
                });
            });

            // Initially select all absolute configs seen across all tests for context
            if (currentTestList.length > 0) {
                const firstTestConfigs = Object.keys(results[currentTestList[0]] || {});
                firstTestConfigs.forEach(c => selectedConfigs.add(c));
            }

            // Populate Test Class Dropdown
            sortedClasses.forEach(c => {
                const opt = document.createElement('option');
                opt.value = c;
                opt.textContent = c;
                classSelect.appendChild(opt);
            });
            classSelect.addEventListener('change', (e) => {
                setClass(e.target.value);
                updateURL(true);
            });

            // Populate initial Test Dropdown
            updateTestDropdown();

            testSelect.addEventListener('change', (e) => {
                setTest(parseInt(e.target.value));
                updateURL(true);
            });

            // Nav buttons
            document.getElementById('prev-test').addEventListener('click', () => { setTest(currentTestIdx - 1); updateURL(true); });
            document.getElementById('next-test').addEventListener('click', () => { setTest(currentTestIdx + 1); updateURL(true); });

            // Keyboard navigation
            document.addEventListener('keydown', (e) => {
                // Ignore if user is focused on the select element to not conflict with native dropdown keys
                if (document.activeElement === testSelect) return;
                
                if (e.key === 'ArrowLeft') {
                    setTest(currentTestIdx - 1);
                    updateURL(true);
                } else if (e.key === 'ArrowRight') {
                    setTest(currentTestIdx + 1);
                    updateURL(true);
                }
            });

            // Toggle Grouping
            toggleGroupBtn.addEventListener('click', (e) => {
                e.preventDefault();
                groupBy = groupBy === 'host' ? 'flavour' : 'host';
                toggleGroupBtn.textContent = groupBy === 'host' ? 'Host' : 'Flavour';
                renderConfigTree();
                updateURL();
            });

            // Select All / None
            document.getElementById('sel-all').addEventListener('click', (e) => {
                e.preventDefault();
                const availableConfigs = Object.keys(results[currentTestList[currentTestIdx]] || {});
                availableConfigs.forEach(c => selectedConfigs.add(c));
                renderConfigTree();
                updateGraph();
                updateURL();
            });
            document.getElementById('sel-none').addEventListener('click', (e) => {
                e.preventDefault();
                const availableConfigs = Object.keys(results[currentTestList[currentTestIdx]] || {});
                availableConfigs.forEach(c => selectedConfigs.delete(c));
                renderConfigTree();
                updateGraph();
                updateURL();
            });

            // Expand All / Collapse All
            document.getElementById('expand-all').addEventListener('click', (e) => {
                e.preventDefault();
                collapsedGroups.clear();
                renderConfigTree();
                updateURL();
            });
            document.getElementById('collapse-all').addEventListener('click', (e) => {
                e.preventDefault();
                const currentTest = currentTestList[currentTestIdx];
                if (!currentTest) return;
                const availableConfigs = Object.keys(results[currentTest] || {});
                availableConfigs.forEach(c => {
                    const parts = c.split('/');
                    const host = parts[0];
                    const flavour = parts[1] || 'unknown';
                    const groupKey = groupBy === 'host' ? host : flavour;
                    collapsedGroups.add(groupKey);
                });
                renderConfigTree();
                updateURL();
            });

            // Axis Toggles
            document.getElementById('log-x').addEventListener('change', (e) => {
                xAxisType = e.target.checked ? 'log' : 'linear';
                updateGraph();
                updateURL();
            });
            document.getElementById('log-y').addEventListener('change', (e) => {
                yAxisType = e.target.checked ? 'log' : 'linear';
                updateGraph();
                updateURL();
            });

            // Debounced scroll listener for main-sweep
            let scrollTimeout;
            sweepTableWrapper.addEventListener('scroll', () => {
                window.currentSweepScroll = sweepTableWrapper.scrollTop;
                if (scrollTimeout) clearTimeout(scrollTimeout);
                scrollTimeout = setTimeout(() => {
                    updateURL();
                }, 200);
            });

            // Popstate listener
            window.addEventListener('popstate', restoreStateFromURL);

            // Initial Render
            if (window.location.search) {
                restoreStateFromURL();
            } else {
                renderConfigTree();
                updateGraph();
            }
        }

        function updateTestDropdown() {
            testSelect.innerHTML = '';
            currentTestList.forEach((t, idx) => {
                const opt = document.createElement('option');
                opt.value = idx;
                opt.textContent = t;
                testSelect.appendChild(opt);
            });
        }

        function setClass(cName) {
            currentClass = cName;
            classSelect.value = cName;
            currentTestList = testClasses[currentClass] || [];
            updateTestDropdown();
            
            // Auto-select all configs for this class's first test if not already present
            if (currentTestList.length > 0) {
                const firstTest = currentTestList[0];
                const availableConfigs = Object.keys(results[firstTest] || {});
                availableConfigs.forEach(c => selectedConfigs.add(c));
            }
            
            setTest(0);
        }

        function setTest(idx) {
            if (idx < 0 || idx >= currentTestList.length) return;
            currentTestIdx = idx;
            testSelect.value = idx;
            renderConfigTree();
            updateGraph();
        }

        function renderConfigTree() {
            const currentTest = currentTestList[currentTestIdx];
            const availableConfigs = Object.keys(results[currentTest] || {});
            
            // Group the configs
            const groups = {};
            availableConfigs.forEach(c => {
                const parts = c.split('/');
                const host = parts[0];
                const flavour = parts[1] || 'unknown';
                
                const groupKey = groupBy === 'host' ? host : flavour;
                const label = groupBy === 'host' ? flavour : host;
                
                if (!groups[groupKey]) groups[groupKey] = [];
                groups[groupKey].push({ config: c, label: label });
            });
            
            configContainer.innerHTML = '';
            
            if (availableConfigs.length === 0) {
                configContainer.innerHTML = '<div style="color: var(--text-muted); font-size: 0.8rem; padding: 10px;">No configurations available for this test.</div>';
                return;
            }

            // Render groups
            Object.keys(groups).sort().forEach(gKey => {
                const groupDiv = document.createElement('div');
                groupDiv.className = 'config-group';
                
                const headerDiv = document.createElement('div');
                headerDiv.className = 'group-header';
                
                const leftWrapper = document.createElement('div');
                leftWrapper.style.display = 'flex';
                leftWrapper.style.alignItems = 'center';
                leftWrapper.style.gap = '8px';
                
                const gCheck = document.createElement('input');
                gCheck.type = 'checkbox';
                
                const children = groups[gKey];
                const selectedCount = children.filter(c => selectedConfigs.has(c.config)).length;
                
                if (selectedCount === children.length && children.length > 0) {
                    gCheck.checked = true;
                    gCheck.indeterminate = false;
                } else if (selectedCount > 0) {
                    gCheck.checked = false;
                    gCheck.indeterminate = true;
                } else {
                    gCheck.checked = false;
                    gCheck.indeterminate = false;
                }
                
                leftWrapper.appendChild(gCheck);
                const gLabel = document.createElement('span');
                gLabel.textContent = gKey;
                leftWrapper.appendChild(gLabel);
                headerDiv.appendChild(leftWrapper);
                
                const collapseIcon = document.createElement('span');
                collapseIcon.textContent = '▼';
                collapseIcon.style.fontSize = '0.65rem';
                collapseIcon.style.width = '12px';
                collapseIcon.style.display = 'inline-block';
                collapseIcon.style.cursor = 'pointer';
                collapseIcon.style.color = 'var(--text-muted)';
                collapseIcon.style.userSelect = 'none';
                collapseIcon.style.textAlign = 'right';
                headerDiv.appendChild(collapseIcon);
                
                const childrenDiv = document.createElement('div');
                childrenDiv.className = 'group-children';
                
                const isCollapsed = collapsedGroups.has(gKey);
                childrenDiv.style.display = isCollapsed ? 'none' : 'flex';
                collapseIcon.textContent = isCollapsed ? '▶' : '▼';

                // Collapse functionality
                collapseIcon.addEventListener('click', (e) => {
                    e.stopPropagation();
                    if (childrenDiv.style.display === 'none') {
                        childrenDiv.style.display = 'flex';
                        collapseIcon.textContent = '▼';
                        collapsedGroups.delete(gKey);
                    } else {
                        childrenDiv.style.display = 'none';
                        collapseIcon.textContent = '▶';
                        collapsedGroups.add(gKey);
                    }
                    updateURL();
                });

                // Selection functionality
                headerDiv.addEventListener('click', (e) => {
                    if (e.target === collapseIcon) return; // handled above
                    if (e.target !== gCheck) {
                        // Toggle logic if clicked on label
                        if (gCheck.indeterminate || !gCheck.checked) {
                            gCheck.checked = true;
                            gCheck.indeterminate = false;
                        } else {
                            gCheck.checked = false;
                            gCheck.indeterminate = false;
                        }
                    }
                    
                    const targetState = gCheck.checked;
                    children.forEach(c => {
                        if (targetState) selectedConfigs.add(c.config);
                        else selectedConfigs.delete(c.config);
                    });
                    
                    renderConfigTree();
                    updateGraph();
                    updateURL();
                });
                
                groupDiv.appendChild(headerDiv);
                
                children.sort((a,b) => a.label.localeCompare(b.label)).forEach(c => {
                    const lbl = document.createElement('label');
                    lbl.className = 'checkbox-label';
                    const chk = document.createElement('input');
                    chk.type = 'checkbox';
                    chk.value = c.config;
                    chk.checked = selectedConfigs.has(c.config);
                    
                    chk.addEventListener('change', (e) => {
                        if (e.target.checked) selectedConfigs.add(c.config);
                        else selectedConfigs.delete(c.config);
                        renderConfigTree();
                        updateGraph();
                        updateURL();
                    });
                    
                    lbl.appendChild(chk);
                    lbl.appendChild(document.createTextNode(c.label));
                    childrenDiv.appendChild(lbl);
                });
                
                groupDiv.appendChild(childrenDiv);
                configContainer.appendChild(groupDiv);
            });
        }

        // Use the Golden Angle approximation to pre-calculate mathematically distinct hues for every absolute config
        const SYMBOLS = ['circle', 'square', 'diamond', 'cross', 'x', 'triangle-up', 'pentagon', 'hexagram', 'star', 'star-diamond'];
        const configVisuals = {};
        
        allConfigs.forEach((c, idx) => {
             // Golden angle guarantees maximally distinct hues over a continuous distribution
             const h = Math.round((idx * 137.508) % 360);
             const sym = SYMBOLS[idx % SYMBOLS.length];
             configVisuals[c] = {
                 color: `hsl(${h}, 85%, 65%)`,
                 symbol: sym
             };
        });

        function getVisuals(config) {
             return configVisuals[config] || { color: '#ccc', symbol: 'circle' };
        }

        function updateGraph() {
            const currentTest = currentTestList[currentTestIdx];
            const testData = results[currentTest] || {};
            const availableConfigs = Object.keys(testData);
            const unit = units[currentTest] || '';
            const unitLower = unit.toLowerCase();
            const lowerIsBetter = unitLower.includes('usec') || unitLower === 'us' || unitLower.includes('[us]') || unitLower.includes('(us)') || unitLower.includes('latency');
            
            const baselineHost = baselineSelect.value;
            const isRelative = baselineHost !== "" && document.getElementById("baseline-enable").checked;
            
            // Check if we have any active traces for this specific test
            const activeTraces = availableConfigs.filter(c => selectedConfigs.has(c));
            
            if (!currentTest || activeTraces.length === 0) {
                Plotly.purge(plotEl);
                graphEmpty.classList.add('active');
                tableEmpty.classList.add('active');
                tableEl.innerHTML = '';
                return;
            }
            graphEmpty.classList.remove('active');
            tableEmpty.classList.remove('active');

            const traces = [];

            // Add traces dynamically maintaining order
            activeTraces.sort().forEach(config => {
                const visuals = getVisuals(config);
                const parts = config.split('/');
                const flavour = parts[1];
                
                let yValues = testData[config];
                
                if (isRelative) {
                    const baselineConfig = `${baselineHost}/${flavour}`;
                    const baselineData = testData[baselineConfig];
                    
                    if (!baselineData) {
                        return; // skip adding this trace entirely
                    } else {
                        yValues = yValues.map((v, i) => {
                            const b = baselineData[i];
                            if (v === null || b === null || b === 0) return null;
                            // Reverse logic for latency (lower is better means positive % is a performance gain)
                            if (lowerIsBetter) {
                                return ((b - v) / b) * 100;
                            } else {
                                return ((v - b) / b) * 100;
                            }
                        });
                    }
                }
                
                traces.push({
                    x: xSizes,
                    y: yValues,
                    type: 'scatter',
                    mode: 'lines+markers',
                    name: config,
                    line: {
                        color: visuals.color,
                        width: 2,
                        shape: 'linear'
                    },
                    marker: {
                        size: 7, // Slightly larger base size to make complex shapes readable
                        color: visuals.color,
                        symbol: visuals.symbol
                    },
                    connectgaps: true, // Propagate the line across missing (null) values
                    hovertemplate: `<b>${config}</b><br>Size: %{x}<br>Value: %{y}${isRelative ? '%' : ''}<extra></extra>`
                });
            });

            // Update title inline
            document.getElementById('graph-title').textContent = currentTest;

            const layout = {
                paper_bgcolor: 'transparent',
                plot_bgcolor: 'transparent',
                font: { family: 'Inter', color: '#94a3b8' },
                xaxis: {
                    title: { text: 'Message Size (Bytes)', font: { color: '#cbd5e1' } },
                    type: xAxisType,
                    gridcolor: 'rgba(255,255,255,0.05)',
                    zerolinecolor: 'rgba(255,255,255,0.1)'
                },
                yaxis: {
                    title: { text: isRelative ? `Relative Performance % (orig: ${unit || 'Value'})` : (unit || 'Value'), font: { color: '#cbd5e1' } },
                    type: isRelative ? 'linear' : yAxisType, // Force linear when in relative % mode
                    gridcolor: 'rgba(255,255,255,0.05)',
                    zerolinecolor: 'rgba(255,255,255,0.2)'
                },
                margin: { l: 60, r: 10, t: 10, b: 40 },
                showlegend: true,
                legend: {
                    y: 0.85,
                    font: { color: '#cbd5e1', size: 12 },
                    bgcolor: 'rgba(15, 23, 42, 0.5)',
                    bordercolor: 'rgba(255,255,255,0.1)',
                    borderwidth: 1
                },
                hovermode: 'closest'
            };

            const configOpts = {
                responsive: true,
                displayModeBar: true,
                displaylogo: false,
                modeBarButtonsToRemove: ['lasso2d', 'select2d']
            };

            Plotly.react(plotEl, traces, layout, configOpts);

            // Trigger table update (we pass absolute data directly, the table calculates its own diffs)
            updateTable(activeTraces, testData, unit);
        }

        // Data Table Sorting State
        let dtSortCol = -1;
        let dtSortAsc = true;

        window.sortDataTable = function(colIdx) {
            const table = document.getElementById('data-table');
            const tbody = table.querySelector('tbody');
            if (!tbody) return;
            const rows = Array.from(tbody.querySelectorAll('tr'));
            
            if (dtSortCol === colIdx) {
                dtSortAsc = !dtSortAsc;
            } else {
                dtSortCol = colIdx;
                dtSortAsc = true;
            }

            rows.sort((a, b) => {
                const cellA = a.children[colIdx].textContent.trim();
                const cellB = b.children[colIdx].textContent.trim();
                
                if (cellA === '-' && cellB !== '-') return dtSortAsc ? 1 : -1;
                if (cellB === '-' && cellA !== '-') return dtSortAsc ? -1 : 1;
                if (cellA === '-' && cellB === '-') return 0;
                
                const numA = parseFloat(cellA);
                const numB = parseFloat(cellB);
                
                if (!isNaN(numA) && !isNaN(numB)) {
                    return dtSortAsc ? numA - numB : numB - numA;
                }
                
                return dtSortAsc ? cellA.localeCompare(cellB) : cellB.localeCompare(cellA);
            });

            const headers = table.querySelectorAll('th');
            headers.forEach((th, i) => {
                th.innerHTML = th.innerHTML.replace(/ <span.*<\\/span>/, '');
                if (i === colIdx) {
                    th.innerHTML += ` <span style="font-size:0.7em; color:var(--text-muted)">${dtSortAsc ? '▲' : '▼'}</span>`;
                }
            });

            tbody.innerHTML = '';
            rows.forEach(row => tbody.appendChild(row));
            updateURL();
        };

        function updateTable(activeTraces, testData, unit) {
            const baselineHost = document.getElementById("baseline-enable").checked ? baselineSelect.value : "";
            // Infer if 'lower is better' based on unit string
            const unitLower = (unit || '').toLowerCase();
            const lowerIsBetter = isLowerBetterFunc(unitLower);

            let html = `<thead><tr><th class="col-fixed" onclick="sortDataTable(0)" style="cursor:pointer;" title="Click to sort">Configuration</th>`;
            xSizes.forEach((size, i) => {
                html += `<th onclick="sortDataTable(${i + 1})" style="cursor:pointer;" title="Click to sort">Size ${size}</th>`;
            });
            html += `</tr></thead><tbody>`;

            activeTraces.forEach(config => {
                const parts = config.split('/');
                const flavour = parts[1];
                const baselineConfig = `${baselineHost}/${flavour}`;
                const baselineData = baselineHost ? testData[baselineConfig] : null;

                if (baselineHost && !baselineData) {
                    return; // Skip adding row if baseline is selected but flavour doesn't exist
                }

                html += `<tr><td class="col-fixed">${config}</td>`;
                const vals = testData[config] || [];

                xSizes.forEach((_, i) => {
                    const val = vals[i];
                    const displayVal = val !== null && val !== undefined ? val : '-';
                    
                    let cellStyle = '';
                    if (baselineHost && baselineData && config !== baselineConfig && val !== null) {
                        const bVal = baselineData[i];
                        if (bVal !== null && bVal !== undefined && bVal !== 0) {
                            const pctDiff = (val - bVal) / bVal; // +0.10 means 10% higher number
                            
                            let isWorse = false;
                            let isBetter = false;
                            // 5% tolerance window
                            if (lowerIsBetter) { // latency
                                if (pctDiff > 0.05) isWorse = true;
                                if (pctDiff < -0.05) isBetter = true;
                            } else { // bandwidth
                                if (pctDiff < -0.05) isWorse = true;
                                if (pctDiff > 0.05) isBetter = true;
                            }
                            
                            if (isWorse) cellStyle = 'background-color: rgba(239, 68, 68, 0.25); color: #fca5a5;';
                            if (isBetter) cellStyle = 'background-color: rgba(34, 197, 94, 0.25); color: #86efac;';
                        }
                    }
                    
                    html += `<td style="${cellStyle}">${displayVal}</td>`;
                });
                html += `</tr>`;
            });

            html += `</tbody>`;
            tableEl.innerHTML = html;
            
            if (dtSortCol !== -1) {
                // temporarily flip asc so that the call flips it back to the current state
                dtSortAsc = !dtSortAsc; 
                sortDataTable(dtSortCol);
            }
        }

        function isLowerBetterFunc(u) {
            return (u || '').includes('usec') || u === 'us' || (u || '').includes('[us]') || (u || '').includes('(us)') || (u || '').includes('latency');
        }

        // Sort State
        let regSortCol = 'diff';
        let regSortAsc = false;

        function runRegressionSweep() {
            const baseline = sweepBaselineSelect.value;
            const target = targetSelect.value;
            const regHead = document.getElementById('regression-thead');
            const regBody = document.getElementById('regression-tbody');
            const emptyState = document.getElementById('regression-empty');

            regBody.innerHTML = '';
            regHead.innerHTML = '';

            // Reset stats
            document.getElementById('stat-evaluated').textContent = "0";
            document.getElementById('stat-regressions').textContent = "0";
            document.getElementById('stat-mean').textContent = "0%";
            document.getElementById('stat-variance').textContent = "0";

            if (!baseline || !target || baseline === target) {
                emptyState.classList.add('active');
                return;
            }

            emptyState.classList.remove('active');
            let regressions = [];
            let allPerfGains = [];
            let totalEvaluated = 0;

            // Gather active envs
            const selectedEnvs = new Set();
            document.querySelectorAll('.env-filter-chk').forEach(chk => {
                if (chk.checked) selectedEnvs.add(chk.value);
            });

            sortedClasses.forEach(cName => {
                const tList = testClasses[cName] || [];
                tList.forEach(testName => {
                    const tData = results[testName] || {};
                    const unit = units[testName] || '';
                    const lowerIsBetter = isLowerBetterFunc((unit || '').toLowerCase());
                    
                    const envs = new Set();
                    Object.keys(tData).forEach(trace => envs.add(trace.split('/')[1]));

                    envs.forEach(env => {
                        if (!selectedEnvs.has(env)) return; // APPLY FILTER
                        
                        const baseData = tData[`${baseline}/${env}`];
                        const targetData = tData[`${target}/${env}`];

                        if (baseData && targetData) {
                            for (let i = 0; i < xSizes.length; i++) {
                                const b = baseData[i];
                                const t = targetData[i];
                                
                                if (b !== null && b !== undefined && b !== 0 && t !== null && t !== undefined && t !== 0) {
                                    totalEvaluated++;
                                    let perfGain = 0;
                                    
                                    if (lowerIsBetter) {
                                        perfGain = ((b - t) / b) * 100; // b=100us, t=50us -> +50%
                                    } else {
                                        perfGain = ((t - b) / b) * 100; // b=100MB, t=150MB -> +50%
                                    }
                                    
                                    allPerfGains.push(perfGain);
                                    let degradation = -perfGain; // if perfGain is -6%, degradation is 6%
                                    
                                    let isSignificant = true;
                                    if (lowerIsBetter && Math.abs(t - b) < 0.15) {
                                        isSignificant = false;
                                    }

                                    if (degradation > 5 && isSignificant) {
                                        regressions.push({
                                            cls: cName,
                                            test: testName,
                                            env: env,
                                            size: xSizes[i],
                                            bVal: b,
                                            tVal: t,
                                            diff: degradation,
                                            perfGain: perfGain,
                                            unit: unit
                                        });
                                    }
                                }
                            }
                        }
                    });
                });
            });

            // Update Statistical Cards
            document.getElementById('stat-evaluated').textContent = totalEvaluated.toLocaleString();
            document.getElementById('stat-regressions').textContent = regressions.length.toLocaleString();
            
            if (totalEvaluated > 0) {
                const sum = allPerfGains.reduce((acc, val) => acc + val, 0);
                const mean = sum / totalEvaluated;
                
                const sqRes = allPerfGains.reduce((acc, val) => acc + Math.pow(val - mean, 2), 0);
                const variance = sqRes / totalEvaluated;
                
                const meanEl = document.getElementById('stat-mean');
                meanEl.textContent = (mean > 0 ? '+' : '') + mean.toFixed(2) + '%';
                meanEl.style.color = mean >= 0 ? '#22c55e' : '#ef4444';
                
                document.getElementById('stat-variance').textContent = variance.toFixed(2);
            }

            if (regressions.length === 0) {
                regBody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding: 24px;">No >5% regressions found for selected environments!</td></tr>';
            } else {
                renderRegressionTable(regressions, target);
            }
        }

        function renderRegressionTable(regressions, target) {
            const regHead = document.getElementById('regression-thead');
            const regBody = document.getElementById('regression-tbody');
            
            regBody.innerHTML = '';
            
            const cols = [
                { id: 'cls', label: 'Test Class', class: 'col-fixed', z: 5 },
                { id: 'test', label: 'Test Name' },
                { id: 'env', label: 'Test Env' },
                { id: 'size', label: 'Size (Bytes)' },
                { id: 'bVal', label: 'Baseline Val' },
                { id: 'tVal', label: 'Target Val' },
                { id: 'diff', label: 'Regression %' }
            ];

            let theadHtml = '<tr>';
            cols.forEach(c => {
                const isSorted = regSortCol === c.id;
                const arrow = isSorted ? (regSortAsc ? ' ▲' : ' ▼') : '';
                const styleStr = c.class ? `class="${c.class}" style="z-index:${c.z}; cursor:pointer;"` : 'style="cursor:pointer;"';
                theadHtml += `<th data-sort="${c.id}" ${styleStr}>${c.label}<span style="font-size:0.7em; color:var(--text-muted)">${arrow}</span></th>`;
            });
            theadHtml += '</tr>';
            regHead.innerHTML = theadHtml;

            // Add sorting listeners
            regHead.querySelectorAll('th').forEach(th => {
                th.addEventListener('click', () => {
                    const id = th.dataset.sort;
                    if (regSortCol === id) {
                        regSortAsc = !regSortAsc;
                    } else {
                        regSortCol = id;
                        regSortAsc = false; // default desc for metric, wait, logic below applies
                    }
                    renderRegressionTable(regressions, target);
                    updateURL();
                });
            });

            // Sort array
            regressions.sort((a,b) => {
                let valA = a[regSortCol];
                let valB = b[regSortCol];
                
                if (typeof valA === 'string') {
                    return regSortAsc ? valA.localeCompare(valB) : valB.localeCompare(valA);
                } else {
                    return regSortAsc ? (valA - valB) : (valB - valA);
                }
            });

            const frag = document.createDocumentFragment();
            regressions.forEach(r => {
                const tr = document.createElement('tr');
                tr.style.cursor = 'pointer';
                tr.onmouseenter = () => tr.style.background = 'rgba(255, 255, 255, 0.1)';
                tr.onmouseleave = () => tr.style.background = 'transparent';
                
                const targetState = Object.assign({}, getState());
                targetState.view = 'explorer';
                targetState.class = r.cls;
                targetState.test = r.test;
                targetState.baseline = sweepBaselineSelect.value;
                targetState.configs = `${sweepBaselineSelect.value}/${r.env},${target}/${r.env}`;
                
                const targetUrl = buildUrlForState(targetState);
                
                tr.innerHTML = `
                    <td class="col-fixed" style="z-index: 1;">${r.cls}</td>
                    <td style="color:#f8fafc; font-weight:600;"><a href="${targetUrl}" class="regression-link" style="color:inherit; text-decoration:underline;">${r.test}</a></td>
                    <td style="color:#60a5fa">${r.env}</td>
                    <td>${r.size}</td>
                    <td>${parseFloat(r.bVal.toFixed(2))} ${r.unit}</td>
                    <td>${parseFloat(r.tVal.toFixed(2))} ${r.unit}</td>
                    <td style="color:#ef4444; font-weight:bold;">-${r.diff.toFixed(2)}%</td>
                `;
                frag.appendChild(tr);
            });
            regBody.appendChild(frag);

            regBody.querySelectorAll('.regression-link').forEach(link => {
                link.addEventListener('click', (e) => {
                    if (e.button === 0 && !e.ctrlKey && !e.metaKey) {
                        e.preventDefault();
                        history.pushState(null, '', link.getAttribute('href'));
                        restoreStateFromURL();
                    }
                });
            });
        }

        function jumpToGraph(cls, test, configCheck) {
            // Trigger mode switch instantly to Explorer
            modeExplorer.click();

            // Switch tabs visually to Graph
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelector('.tab-btn[data-target="pane-graph"]').classList.add('active');
            document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
            document.getElementById('pane-graph').classList.add('active');

            // Set state

            setClass(cls);
            const tIdx = currentTestList.indexOf(test);
            if (tIdx > -1) setTest(tIdx);

            // Select Target Env Config
            selectedConfigs.add(configCheck);
            
            renderConfigTree();
            updateGraph();
            
            setTimeout(() => { Plotly.Plots.resize(plotEl); }, 50);
        }

        // Go!
        document.addEventListener('DOMContentLoaded', init);
    </script>
</body>
</html>
"""

def generate_report():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.dirname(script_dir) # Parse CSVs from the parent directory
    data = parse_csvs(data_dir)
    
    # Serialize data to JSON
    json_payload = json.dumps(data)
    
    # Render HTML
    html_content = HTML_TEMPLATE.replace('// JSON_PAYLOAD_HERE //;', json_payload + ';')
    
    out_path = os.path.join(data_dir, 'hpc_report.html')
    with open(out_path, 'w') as f:
        f.write(html_content)
        
    print(f"Report generated successfully: {out_path}")
    
    # Auto-open with xdg-open
    try:
        print("Opening in browser via xdg-open...")
        subprocess.run(["xdg-open", out_path], check=True)
    except Exception as e:
        print(f"Failed to auto-open the browser: {e}")

if __name__ == "__main__":
    generate_report()
