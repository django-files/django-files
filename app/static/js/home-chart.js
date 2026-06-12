// Renders the upload-activity chart on the home dashboard.
// Reads data from json_script tags emitted in home.html and supports a
// scope toggle (mine/server) when both data sets are present.

;(function () {
    const root = document.getElementById('home-chart')
    if (!root || typeof echarts === 'undefined') return

    function readJson(id) {
        const el = document.getElementById(id)
        return el ? JSON.parse(el.textContent) : null
    }

    const mineDays = readJson('home-chart-days')
    if (!mineDays) return

    const scopes = {
        mine: {
            label: 'My',
            days: mineDays,
            files: readJson('home-chart-files'),
            size: readJson('home-chart-size'),
            shorts: readJson('home-chart-shorts'),
        },
    }

    // Smooth deltas then reintegrate so the trend is smooth but the cumulative
    // total stays grounded (doesn't undercount reality).
    function smoothDeltas(data, win) {
        if (data.length < 2) return data.slice()
        const w = Math.min(win, Math.max(1, Math.floor(data.length / 4)))
        const deltas = data.map((v, i) => (i === 0 ? 0 : v - data[i - 1]))
        const smoothed = deltas.map((_, i) => {
            const lo = Math.max(0, i - w + 1)
            const slice = deltas.slice(lo, i + 1)
            return slice.reduce((a, b) => a + b, 0) / slice.length
        })
        const out = [data[0]]
        for (let i = 1; i < data.length; i++) {
            out.push(Math.round(out[i - 1] + smoothed[i]))
        }
        return out
    }

    const serverDays = readJson('home-chart-server-days')
    if (serverDays) {
        scopes.server = {
            label: 'Server',
            days: serverDays,
            files: smoothDeltas(readJson('home-chart-server-files'), 7),
            size: smoothDeltas(readJson('home-chart-server-size'), 7),
            shorts: smoothDeltas(readJson('home-chart-server-shorts'), 7),
        }
    }

    const isDark = document.documentElement.dataset.bsTheme !== 'light'
    const textColor = isDark ? 'rgba(255,255,255,0.65)' : 'rgba(0,0,0,0.55)'
    const gridColor = isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.07)'
    const chart = echarts.init(root, isDark ? 'dark' : null)

    function bytesHuman(bytes) {
        if (bytes === 0) return '0 B'
        const units = ['B', 'KB', 'MB', 'GB', 'TB']
        const i = Math.floor(Math.log(bytes) / Math.log(1024))
        return (bytes / Math.pow(1024, i)).toFixed(1) + ' ' + units[i]
    }

    const metricCfg = {
        files: {
            label: 'Files',
            color: '#0d6efd',
            leftPad: 40,
            formatter: undefined,
        },
        size: {
            label: 'Size',
            color: '#0dcaf0',
            leftPad: 64,
            formatter: bytesHuman,
        },
        shorts: {
            label: 'Shorts',
            color: '#198754',
            leftPad: 40,
            formatter: undefined,
        },
    }

    let currentScope = 'mine'
    let currentMetric = 'files'

    function buildOption(scope, metric) {
        const s = scopes[scope]
        const m = metricCfg[metric]
        return {
            backgroundColor: 'transparent',
            grid: { top: 16, bottom: 30, left: m.leftPad, right: 16 },
            tooltip: {
                trigger: 'axis',
                formatter: m.formatter
                    ? (p) =>
                          p[0].name +
                          '<br/>' +
                          p[0].marker +
                          ' ' +
                          m.label +
                          ': ' +
                          m.formatter(p[0].value)
                    : undefined,
            },
            xAxis: {
                type: 'category',
                data: s.days,
                axisLine: { lineStyle: { color: gridColor } },
                axisLabel: { color: textColor, fontSize: 11 },
                axisTick: { show: false },
            },
            yAxis: {
                type: 'value',
                splitLine: { lineStyle: { color: gridColor } },
                axisLabel: {
                    color: textColor,
                    fontSize: 11,
                    formatter: m.formatter,
                },
            },
            series: [
                {
                    name: m.label,
                    type: 'line',
                    data: s[metric],
                    smooth: true,
                    symbol: 'circle',
                    symbolSize: 5,
                    lineStyle: { width: 2 },
                    areaStyle: { opacity: 0.12 },
                    itemStyle: { color: m.color },
                },
            ],
        }
    }

    function setActiveBtn(group, key, attr) {
        const dsKey = attr.replace('data-', '')
        group.querySelectorAll('[' + attr + ']').forEach((b) => {
            const active = b.dataset[dsKey] === key
            b.classList.toggle('active', active)
            b.classList.toggle('btn-secondary', active)
            b.classList.toggle('btn-outline-secondary', !active)
        })
    }

    function updateChartTitle() {
        const titleEl = document.getElementById('home-chart-title')
        if (!titleEl) return
        const scopeLabel = scopes[currentScope].label
        const smoothNote =
            currentScope === 'server'
                ? ' <small class="text-muted fw-normal" style="font-size:0.72rem;">7-day avg</small>'
                : ''
        titleEl.innerHTML =
            '<i class="fa-solid fa-chart-line opacity-75"></i> ' +
            scopeLabel +
            ' Upload Activity' +
            smoothNote
    }

    function updateStatCards() {
        document
            .getElementById('stat-cards-mine')
            ?.classList.toggle('d-none', currentScope === 'server')
        document
            .getElementById('stat-cards-server')
            ?.classList.toggle('d-none', currentScope === 'mine')
    }

    chart.setOption(buildOption(currentScope, currentMetric))
    window.addEventListener('resize', () => chart.resize())

    const scopeToggle = document.getElementById('home-scope-toggle')
    if (scopeToggle) {
        scopeToggle.addEventListener('click', (e) => {
            const btn = e.target.closest('[data-scope]')
            if (!btn) return
            currentScope = btn.dataset.scope
            setActiveBtn(scopeToggle, currentScope, 'data-scope')
            updateChartTitle()
            updateStatCards()
            chart.setOption(buildOption(currentScope, currentMetric))
        })
    }

    const metricToggle = document.getElementById('home-chart-toggle')
    metricToggle?.addEventListener('click', (e) => {
        const btn = e.target.closest('[data-metric]')
        if (!btn) return
        currentMetric = btn.dataset.metric
        setActiveBtn(metricToggle, currentMetric, 'data-metric')
        chart.setOption(buildOption(currentScope, currentMetric))
    })
})()
