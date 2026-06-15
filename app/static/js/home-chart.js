// Fetches stats data for the home dashboard and renders stat cards + activity chart.

;(function () {
    const chartBody = document.getElementById('home-chart-body')
    if (!chartBody) return
    const statsUrl = chartBody.dataset.statsUrl
    if (!statsUrl) return

    function renderStatCards(cards, containerId) {
        const el = document.getElementById(containerId)
        if (!el) return
        el.innerHTML = cards
            .map(
                (c) => `
            <div class="col-sm-6 col-xl">
                <div class="dash-stat-card h-100 d-flex align-items-center gap-3">
                    <div class="dash-stat-icon text-bg-${c.bg}">
                        <i class="${c.icon}"></i>
                    </div>
                    <div class="flex-grow-1 min-w-0 dash-stat-text">
                        <div class="dash-stat-value">${c.value}</div>
                        <div class="dash-stat-labels">
                            <div class="dash-stat-label">${c.label}</div>
                            ${c.sublabel ? `<div class="dash-stat-sublabel">${c.sublabel}</div>` : ''}
                        </div>
                    </div>
                </div>
            </div>`
            )
            .join('')
    }

    function initChart(data, serverData) {
        const chartEl = document.getElementById('home-chart')
        const loadingEl = document.getElementById('home-chart-loading')
        const emptyEl = document.getElementById('home-chart-empty')

        if (!data.has_stats || !data.chart) {
            loadingEl?.classList.add('d-none')
            emptyEl?.classList.remove('d-none')
            return
        }

        const scopes = {
            mine: {
                label: 'My',
                days: data.chart.days,
                files: data.chart.files,
                size: data.chart.size,
                shorts: data.chart.shorts,
            },
        }

        if (serverData?.chart) {
            scopes.server = {
                label: 'Server',
                days: serverData.chart.days,
                files: serverData.chart.files,
                size: serverData.chart.size,
                shorts: serverData.chart.shorts,
            }
        }

        loadingEl?.classList.add('d-none')
        chartEl.style.display = ''

        document.getElementById('home-chart-toggle')?.classList.remove('d-none')
        if (serverData?.chart) {
            document
                .getElementById('home-scope-toggle')
                ?.classList.remove('d-none')
        }
        const updatedEl = document.getElementById('home-stats-updated')
        if (updatedEl && data.updated_at) {
            updatedEl.textContent = `Updated: ${data.updated_at}`
            updatedEl.classList.remove('d-none')
        }

        const isDark = document.documentElement.dataset.bsTheme !== 'light'
        const textColor = isDark ? 'rgba(255,255,255,0.65)' : 'rgba(0,0,0,0.55)'
        const gridColor = isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.07)'
        const chart = echarts.init(chartEl, isDark ? 'dark' : null)

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
            titleEl.innerHTML =
                '<i class="fa-solid fa-chart-line opacity-75"></i> ' +
                scopeLabel +
                ' Upload Activity'
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
            updateChartTitle()
            chart.setOption(buildOption(currentScope, currentMetric))
        })
    }

    function fetchJson(url) {
        return fetch(url, { credentials: 'same-origin' }).then((r) => {
            if (!r.ok) throw new Error(r.status)
            return r.json()
        })
    }

    const serverStatsUrl = chartBody.dataset.serverStatsUrl
    const fetches = [
        fetchJson(statsUrl),
        serverStatsUrl ? fetchJson(serverStatsUrl) : Promise.resolve(null),
    ]

    Promise.all(fetches)
        .then(([data, serverData]) => {
            if (data.stat_cards?.length) {
                renderStatCards(data.stat_cards, 'stat-cards-mine')
            }
            if (serverData?.stat_cards?.length) {
                renderStatCards(serverData.stat_cards, 'stat-cards-server')
            }
            if (!data.has_stats) {
                document
                    .getElementById('home-no-stats-alert')
                    ?.classList.remove('d-none')
            }
            if (typeof echarts !== 'undefined') {
                initChart(data, serverData)
            }
        })
        .catch(() => {
            const loadingEl = document.getElementById('home-chart-loading')
            if (loadingEl)
                loadingEl.innerHTML =
                    '<span class="small text-muted">Could not load stats.</span>'
        })
})()
