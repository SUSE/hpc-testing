#!/usr/bin/env python3
import glob
import csv
import json
import os
import subprocess

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
        # Extract config from path: results/<distro>/<testenv>.csv
        parts = filepath.split(os.sep)
        if len(parts) >= 3:
            distro = parts[-2]
            testenv = parts[-1].replace('.csv', '')
            config = f"{distro}/{testenv}"
            data["configs"].add(config)
            
            with open(filepath, 'r') as f:
                reader = csv.reader(f)
                header = next(reader, None)
                if not header:
                    continue
                
                # Sizes are from column 2 onwards
                if not data["sizes"]:
                    try:
                        data["sizes"] = [int(x) for x in header[2:]]
                    except ValueError:
                        pass # Ignore parsing issues for sizes and keep going
                
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
        }

        /* Sidebar Styling */
        .sidebar {
            width: 340px;
            flex-shrink: 0;
            background: var(--panel-bg);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border-right: 1px solid var(--border-color);
            padding: 24px;
            display: flex;
            flex-direction: column;
            gap: 20px;
            overflow-y: auto;
            box-shadow: var(--shadow);
            z-index: 10;
            transition: margin-left 0.3s ease;
        }
        
        .sidebar.collapsed {
            margin-left: -340px;
        }

        .control-group {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        .control-group label.group-title {
            font-size: 0.875rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
        }

        select {
            background-color: rgba(15, 23, 42, 0.8);
            background-image: url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3e%3cpolyline points='6 9 12 15 18 9'%3e%3c/polyline%3e%3c/svg%3e");
            background-repeat: no-repeat;
            background-position: right 14px center;
            background-size: 16px;
            color: var(--text-main);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 10px 40px 10px 14px;
            font-family: inherit;
            font-size: 0.95rem;
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
            padding: 4px 6px;
            border-radius: 4px;
            font-family: inherit;
            font-size: 1rem;
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
            width: 14px;
            height: 14px;
            stroke: currentColor;
            stroke-width: 2;
        }

        .checkbox-container {
            display: flex;
            flex-direction: column;
            gap: 4px;
            flex: 1;
            overflow-y: auto;
            padding-right: 8px;
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
            gap: 10px;
            font-size: 0.85rem;
            cursor: pointer;
            padding: 4px 8px;
            border-radius: 6px;
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
            width: 16px;
            height: 16px;
            border: 1px solid var(--border-color);
            border-radius: 4px;
            display: grid;
            place-content: center;
            cursor: pointer;
            transition: all 0.2s;
        }

        input[type="checkbox"]::before {
            content: "";
            width: 10px;
            height: 10px;
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
            margin-bottom: 8px;
        }

        .group-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
            font-size: 0.9rem;
            font-weight: 600;
            cursor: pointer;
            padding: 8px 10px;
            border-radius: 6px;
            background: rgba(255, 255, 255, 0.05);
            transition: background 0.2s;
            color: var(--accent-hover);
        }

        .group-header:hover {
            background: rgba(255, 255, 255, 0.1);
        }

        .group-children {
            padding-left: 12px;
            margin-top: 4px;
            display: flex;
            flex-direction: column;
            gap: 2px;
        }

        /* Tabs Styling */
        .tabs {
            position: absolute;
            top: 24px;
            right: 24px;
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
            padding: 6px 12px;
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
            padding: 24px;
            display: flex;
            flex-direction: column;
            position: relative;
            min-width: 0;
            background: transparent;
        }

        .sidebar-toggle {
            position: absolute;
            top: 24px;
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
            background: var(--panel-bg);
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
            border: 1px solid var(--border-color);
            border-radius: var(--radius);
            box-shadow: var(--shadow);
            padding: 16px;
            padding-top: 48px; /* space for absolute tabs */
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
            font-size: 1.1rem;
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
            font-size: 0.85rem;
            text-align: right;
            margin: 0;
        }
        
        .data-table th, .data-table td {
            padding: 8px 16px;
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
            <div style="display: flex; flex-direction: column; gap: 12px; padding-bottom: 16px; border-bottom: 1px solid var(--border-color);">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="font-weight: 600; width: 65px; color: var(--text-muted); font-size: 0.85rem;">Class:</span>
                    <select id="class-select" style="flex: 1; padding: 6px 12px;"></select>
                </div>
                
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="font-weight: 600; width: 65px; color: var(--text-muted); font-size: 0.85rem;">Test:</span>
                    <div style="display: flex; gap: 8px; align-items: center; flex: 1;">
                        <button class="nav-btn" id="prev-test" title="Previous Test (Left Arrow)">
                            <svg viewBox="0 0 24 24" fill="none" class="nav-icon"><polyline points="15 18 9 12 15 6"></polyline></svg>
                        </button>
                        <select id="test-select" style="flex: 1; padding: 6px 12px; background-image: none; padding-right: 12px;"></select>
                        <button class="nav-btn" id="next-test" title="Next Test (Right Arrow)">
                            <svg viewBox="0 0 24 24" fill="none" class="nav-icon"><polyline points="9 18 15 12 9 6"></polyline></svg>
                        </button>
                    </div>
                </div>
            </div>

            <div class="control-group" style="padding-bottom: 16px; border-bottom: 1px solid var(--border-color);">
                <div style="display: flex; gap: 16px; margin-bottom: 12px;">
                    <label class="checkbox-label" style="padding: 0;"><input type="checkbox" id="log-x" checked> Log X</label>
                    <label class="checkbox-label" style="padding: 0;"><input type="checkbox" id="log-y"> Log Y</label>
                </div>
                
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="font-weight: 600; width: 65px; color: var(--text-muted); font-size: 0.85rem;">Baseline:</span>
                    <select id="baseline-select" style="flex: 1; padding: 6px 12px;">
                        <option value="">None</option>
                    </select>
                </div>
            </div>

            <div class="control-group" style="flex: 1; overflow: hidden; display: flex; flex-direction: column;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <label class="group-title">Configurations</label>
                    <div style="display: flex; gap: 8px; font-size: 0.75rem;">
                        <span style="color: var(--text-muted);">Group:</span>
                        <a href="#" id="toggle-groupby" style="color: var(--accent); text-decoration: none;">Distro</a>
                    </div>
                </div>
                <div style="display: flex; justify-content: flex-end; gap: 8px; margin-bottom: 8px;">
                    <a href="#" id="sel-all" style="font-size: 0.75rem; color: var(--accent); text-decoration: none;">Select All</a>
                    <a href="#" id="sel-none" style="font-size: 0.75rem; color: var(--text-muted); text-decoration: none;">Clear</a>
                </div>
                <div class="checkbox-container" id="config-checkboxes">
                    <!-- Checkboxes injected by JS -->
                </div>
            </div>
        </div>

        <!-- Main Graph Area -->
        <div class="main-content">
            <button id="sidebar-toggle" class="sidebar-toggle" title="Toggle Sidebar">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="15 18 9 12 15 6"></polyline>
                </svg>
            </button>
            <div id="graph-title" style="position: absolute; top: 29px; left: 40px; z-index: 20; font-size: 1.1rem; font-weight: 600; color: #f8fafc;"></div>
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
        let xAxisType = 'log';
        let yAxisType = 'linear';
        let groupBy = 'distro'; // 'distro' or 'testenv'

        // DOM Elements
        const sidebarEl = document.querySelector('.sidebar');
        const sidebarToggle = document.getElementById('sidebar-toggle');
        const classSelect = document.getElementById('class-select');
        const testSelect = document.getElementById('test-select');
        const configContainer = document.getElementById('config-checkboxes');
        const baselineSelect = document.getElementById('baseline-select');
        const graphEmpty = document.getElementById('graph-empty');
        const tableEmpty = document.getElementById('table-empty');
        const plotEl = document.getElementById('plot');
        const tableEl = document.getElementById('data-table');
        const toggleGroupBtn = document.getElementById('toggle-groupby');

        function init() {
            // Sidebar toggle logic
            sidebarToggle.addEventListener('click', () => {
                sidebarEl.classList.toggle('collapsed');
                setTimeout(() => {
                    Plotly.Plots.resize(plotEl);
                }, 300); // Trigger resize after animation
            });

            // Populate Baselines
            const allDistrosSet = new Set();
            allConfigs.forEach(c => allDistrosSet.add(c.split('/')[0]));
            Array.from(allDistrosSet).sort().forEach(d => {
                const opt = document.createElement('option');
                opt.value = d;
                opt.textContent = d;
                baselineSelect.appendChild(opt);
            });

            baselineSelect.addEventListener('change', updateGraph);

            // Tab switching logic
            document.querySelectorAll('.tab-btn').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                    e.target.classList.add('active');
                    
                    document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
                    document.getElementById(e.target.dataset.target).classList.add('active');
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
            });

            // Populate initial Test Dropdown
            updateTestDropdown();

            testSelect.addEventListener('change', (e) => {
                setTest(parseInt(e.target.value));
            });

            // Nav buttons
            document.getElementById('prev-test').addEventListener('click', () => setTest(currentTestIdx - 1));
            document.getElementById('next-test').addEventListener('click', () => setTest(currentTestIdx + 1));

            // Keyboard navigation
            document.addEventListener('keydown', (e) => {
                // Ignore if user is focused on the select element to not conflict with native dropdown keys
                if (document.activeElement === testSelect) return;
                
                if (e.key === 'ArrowLeft') {
                    setTest(currentTestIdx - 1);
                } else if (e.key === 'ArrowRight') {
                    setTest(currentTestIdx + 1);
                }
            });

            // Toggle Grouping
            toggleGroupBtn.addEventListener('click', (e) => {
                e.preventDefault();
                groupBy = groupBy === 'distro' ? 'testenv' : 'distro';
                toggleGroupBtn.textContent = groupBy === 'distro' ? 'Distro' : 'Testenv';
                renderConfigTree();
            });

            // Select All / None
            document.getElementById('sel-all').addEventListener('click', (e) => {
                e.preventDefault();
                const availableConfigs = Object.keys(results[currentTestList[currentTestIdx]] || {});
                availableConfigs.forEach(c => selectedConfigs.add(c));
                renderConfigTree();
                updateGraph();
            });
            document.getElementById('sel-none').addEventListener('click', (e) => {
                e.preventDefault();
                const availableConfigs = Object.keys(results[currentTestList[currentTestIdx]] || {});
                availableConfigs.forEach(c => selectedConfigs.delete(c));
                renderConfigTree();
                updateGraph();
            });

            // Axis Toggles
            document.getElementById('log-x').addEventListener('change', (e) => {
                xAxisType = e.target.checked ? 'log' : 'linear';
                updateGraph();
            });
            document.getElementById('log-y').addEventListener('change', (e) => {
                yAxisType = e.target.checked ? 'log' : 'linear';
                updateGraph();
            });

            // Initial Render
            renderConfigTree();
            updateGraph();
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
                const distro = parts[0];
                const testenv = parts[1] || 'unknown';
                
                const groupKey = groupBy === 'distro' ? distro : testenv;
                const label = groupBy === 'distro' ? testenv : distro;
                
                if (!groups[groupKey]) groups[groupKey] = [];
                groups[groupKey].push({ config: c, label: label });
            });
            
            configContainer.innerHTML = '';
            
            if (availableConfigs.length === 0) {
                configContainer.innerHTML = '<div style="color: var(--text-muted); font-size: 0.85rem; padding: 10px;">No configurations available for this test.</div>';
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
                leftWrapper.style.gap = '10px';
                
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
                collapseIcon.style.fontSize = '0.7rem';
                collapseIcon.style.width = '14px';
                collapseIcon.style.display = 'inline-block';
                collapseIcon.style.cursor = 'pointer';
                collapseIcon.style.color = 'var(--text-muted)';
                collapseIcon.style.userSelect = 'none';
                collapseIcon.style.textAlign = 'right';
                headerDiv.appendChild(collapseIcon);
                
                const childrenDiv = document.createElement('div');
                childrenDiv.className = 'group-children';

                // Collapse functionality
                collapseIcon.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const isCollapsed = childrenDiv.style.display === 'none';
                    childrenDiv.style.display = isCollapsed ? 'flex' : 'none';
                    collapseIcon.textContent = isCollapsed ? '▼' : '▶';
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
        
        const allConfigsSet = new Set();
        Object.values(results).forEach(cfgObj => {
            Object.keys(cfgObj).forEach(c => allConfigsSet.add(c));
        });
        const allConfigs = Array.from(allConfigsSet).sort();
        
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
            
            const baselineDistro = baselineSelect.value;
            const isRelative = baselineDistro !== "";
            
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
                const testenv = parts[1];
                
                let yValues = testData[config];
                
                if (isRelative) {
                    const baselineConfig = `${baselineDistro}/${testenv}`;
                    const baselineData = testData[baselineConfig];
                    
                    if (!baselineData) {
                        yValues = yValues.map(() => null);
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
                margin: { l: 60, r: 20, t: 40, b: 60 },
                showlegend: true,
                legend: {
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

        function updateTable(activeTraces, testData, unit) {
            const baselineDistro = baselineSelect.value;
            // Infer if 'lower is better' based on unit string
            const unitLower = (unit || '').toLowerCase();
            const lowerIsBetter = unitLower.includes('usec') || unitLower === 'us' || unitLower.includes('[us]') || unitLower.includes('(us)') || unitLower.includes('latency');

            let html = `<thead><tr><th class="col-fixed">Configuration</th>`;
            xSizes.forEach(size => {
                html += `<th>Size ${size}</th>`;
            });
            html += `</tr></thead><tbody>`;

            activeTraces.forEach(config => {
                html += `<tr><td class="col-fixed">${config}</td>`;
                const vals = testData[config] || [];
                
                const parts = config.split('/');
                const testenv = parts[1];
                const baselineConfig = `${baselineDistro}/${testenv}`;
                const baselineData = baselineDistro ? testData[baselineConfig] : null;

                xSizes.forEach((_, i) => {
                    const val = vals[i];
                    const displayVal = val !== null && val !== undefined ? val : '-';
                    
                    let cellStyle = '';
                    if (baselineDistro && baselineData && config !== baselineConfig && val !== null) {
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
        }

        // Go!
        document.addEventListener('DOMContentLoaded', init);
    </script>
</body>
</html>
"""

def generate_report():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    data = parse_csvs(root_dir)
    
    # Serialize data to JSON
    json_payload = json.dumps(data)
    
    # Render HTML
    html_content = HTML_TEMPLATE.replace('// JSON_PAYLOAD_HERE //;', json_payload + ';')
    
    out_path = os.path.join(root_dir, 'hpc_report.html')
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
