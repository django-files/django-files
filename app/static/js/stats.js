// Stats utilities, home dashboard chart, and stats page logic.
// Loaded as a plain script on both the home page and the stats page.
// Each page's IIFE bails out immediately if its root element is absent.

function bytesHuman(bytes) {
    if (!bytes || bytes === 0) return '0 B'
    const units = ['B', 'KB', 'MB', 'GB', 'TB']
    const i = Math.floor(Math.log(bytes) / Math.log(1024))
    return (bytes / Math.pow(1024, i)).toFixed(1) + ' ' + units[i]
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

function buildChartOption(data, metric) {
    const m = metricCfg[metric]
    const isDark = document.documentElement.dataset.bsTheme !== 'light'
    const textColor = isDark ? 'rgba(255,255,255,0.65)' : 'rgba(0,0,0,0.55)'
    const gridColor = isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.07)'
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
            data: data.days,
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
                data: data[metric],
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

function fetchStatsJson(url) {
    return fetch(url, { credentials: 'same-origin' }).then((r) => {
        if (!r.ok) throw new Error(r.status)
        return r.json()
    })
}

$(document).on('click', '.updateStatsBtn', function () {
    $.ajax({
        type: 'POST',
        url: $(this).attr('data-target-url'),
        headers: { 'X-CSRFToken': csrftoken },
        success: function () {
            show_toast('Stats processing queued.', 'info')
            document.dispatchEvent(new CustomEvent('stats:reload'))
        },
        error: messageErrorHandler,
        cache: false,
        contentType: false,
        processData: false,
    })
})

// ── Home dashboard chart ──────────────────────────────────────────────────────
;(function () {
    const chartBody = document.getElementById('home-chart-body')
    if (!chartBody) return
    const statsUrl = chartBody.dataset.statsUrl
    if (!statsUrl) return
    const serverStatsUrl = chartBody.dataset.serverStatsUrl

    let chart = null
    let scopes = {}
    let currentScope = serverStatsUrl ? 'server' : 'mine'
    let currentMetric = 'files'
    let mimeTypes = { mine: [], server: [] }

    function renderStatCards(cards, containerId, scope) {
        const el = document.getElementById(containerId)
        if (!el) return
        el.innerHTML = cards
            .map((c) => {
                const mimeAttr =
                    c.modal === 'mime' ? ` data-mime-scope="${scope}"` : ''
                const clickable =
                    c.modal === 'mime' ? ' dash-stat-card--clickable' : ''
                const title =
                    c.modal === 'mime'
                        ? ' title="View file type breakdown"'
                        : ''
                return `
            <div class="col-sm-6 col-xl"${mimeAttr}${title}>
                <div class="dash-stat-card${clickable} h-100 d-flex align-items-center gap-3">
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
            })
            .join('')
    }

    function openMimeModal(scope) {
        const types = mimeTypes[scope] || []
        const titleEl = document.getElementById('mime-modal-label')
        if (titleEl)
            titleEl.textContent =
                scope === 'server' ? 'Server File Types' : 'My File Types'
        const tbody = document.getElementById('mime-modal-tbody')
        if (!tbody) return
        tbody.innerHTML = types.length
            ? types
                  .map(
                      (t) => `<tr>
                <td class="font-monospace small">${t.mime}</td>
                <td class="text-end">${t.count.toLocaleString()}</td>
                <td class="text-end">${t.human_size}</td>
            </tr>`
                  )
                  .join('')
            : '<tr><td colspan="3" class="text-center text-muted py-3">No data available</td></tr>'
        bootstrap.Modal.getOrCreateInstance(
            document.getElementById('mime-modal')
        ).show()
    }

    function setupMimeClickDelegation() {
        ;['stat-cards-mine', 'stat-cards-server'].forEach((id) => {
            const el = document.getElementById(id)
            if (!el) return
            el.addEventListener('click', (e) => {
                const col = e.target.closest('[data-mime-scope]')
                if (!col) return
                openMimeModal(col.dataset.mimeScope)
            })
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

    function setUpdatedLabel(updatedAt) {
        const updatedEl = document.getElementById('home-stats-updated')
        if (updatedEl && updatedAt) {
            updatedEl.textContent = `Updated: ${updatedAt}`
            updatedEl.classList.remove('d-none')
        }
    }

    function buildScopes(data, serverData) {
        scopes.mine = {
            label: 'My',
            days: data.chart.days,
            files: data.chart.files,
            size: data.chart.size,
            shorts: data.chart.shorts,
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

        buildScopes(data, serverData)

        loadingEl?.classList.add('d-none')
        chartEl.style.display = ''

        document.getElementById('home-chart-toggle')?.classList.remove('d-none')
        const scopeToggle = document.getElementById('home-scope-toggle')
        if (serverData?.chart && scopeToggle) {
            scopeToggle.classList.remove('d-none')
            setActiveBtn(scopeToggle, currentScope, 'data-scope')
        }
        updateChartTitle()
        updateStatCards()
        setUpdatedLabel(data.updated_at)

        const isDark = document.documentElement.dataset.bsTheme !== 'light'
        chart = echarts.init(chartEl, isDark ? 'dark' : null)
        chart.setOption(buildChartOption(scopes[currentScope], currentMetric))
        chart.resize()
        window.addEventListener('resize', () => chart.resize())

        if (scopeToggle) {
            scopeToggle.addEventListener('click', (e) => {
                const btn = e.target.closest('[data-scope]')
                if (!btn) return
                currentScope = btn.dataset.scope
                setActiveBtn(scopeToggle, currentScope, 'data-scope')
                updateChartTitle()
                updateStatCards()
                chart.setOption(
                    buildChartOption(scopes[currentScope], currentMetric)
                )
            })
        }

        const metricToggle = document.getElementById('home-chart-toggle')
        metricToggle?.addEventListener('click', (e) => {
            const btn = e.target.closest('[data-metric]')
            if (!btn) return
            currentMetric = btn.dataset.metric
            setActiveBtn(metricToggle, currentMetric, 'data-metric')
            updateChartTitle()
            chart.setOption(
                buildChartOption(scopes[currentScope], currentMetric)
            )
        })
    }

    function refreshChartData(data, serverData) {
        if (!chart || !data.has_stats || !data.chart) return
        buildScopes(data, serverData)
        setUpdatedLabel(data.updated_at)
        chart.setOption(buildChartOption(scopes[currentScope], currentMetric))
    }

    function loadStats(isRefresh = false) {
        const fetches = [
            fetchStatsJson(statsUrl),
            serverStatsUrl
                ? fetchStatsJson(serverStatsUrl)
                : Promise.resolve(null),
        ]

        return Promise.all(fetches)
            .then(([data, serverData]) => {
                if (data.types?.length) mimeTypes.mine = data.types
                if (serverData?.types?.length)
                    mimeTypes.server = serverData.types

                if (data.stat_cards?.length) {
                    renderStatCards(data.stat_cards, 'stat-cards-mine', 'mine')
                }
                if (serverData?.stat_cards?.length) {
                    renderStatCards(
                        serverData.stat_cards,
                        'stat-cards-server',
                        'server'
                    )
                }
                if (!data.has_stats) {
                    document
                        .getElementById('home-no-stats-alert')
                        ?.classList.remove('d-none')
                }
                if (typeof echarts !== 'undefined') {
                    if (isRefresh) {
                        refreshChartData(data, serverData)
                    } else {
                        initChart(data, serverData)
                    }
                }
            })
            .catch(() => {
                const loadingEl = document.getElementById('home-chart-loading')
                if (loadingEl)
                    loadingEl.innerHTML =
                        '<span class="small text-muted">Could not load stats.</span>'
            })
    }

    setupMimeClickDelegation()
    loadStats()

    document.addEventListener('stats:reload', () => {
        setTimeout(() => loadStats(true), 3000)
    })
})()

// ── Stats page ────────────────────────────────────────────────────────────────
;(function () {
    const body = document.getElementById('stats-page-body')
    if (!body) return
    const statsUrl = body.dataset.statsUrl
    if (!statsUrl) return
    const serverStatsUrl = body.dataset.serverStatsUrl

    let chart = null
    let chartData = null
    let currentMetric = 'files'
    let currentScope = serverStatsUrl ? 'server' : 'mine'
    const scopeData = { mine: null, server: null }

    function renderCards(cards) {
        const el = document.getElementById('stats-page-cards')
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

    function renderMimeTable(types) {
        const tbody = document.getElementById('stats-mime-tbody')
        if (!tbody) return
        tbody.innerHTML = types?.length
            ? types
                  .map(
                      (t) => `<tr>
                <td class="font-monospace small ps-3">${t.mime}</td>
                <td class="text-end">${t.count.toLocaleString()}</td>
                <td class="text-end pe-3">${t.human_size}</td>
            </tr>`
                  )
                  .join('')
            : '<tr><td colspan="3" class="text-center text-muted py-3">No data available</td></tr>'
    }

    function initChart() {
        if (!chartData) return
        const chartEl = document.getElementById('stats-chart')
        if (!chartEl) return
        const isDark = document.documentElement.dataset.bsTheme !== 'light'
        chart = echarts.init(chartEl, isDark ? 'dark' : null)
        chart.setOption(buildChartOption(chartData, currentMetric))
        window.addEventListener('resize', () => chart?.resize())

        const metricToggle = document.getElementById('stats-chart-toggle')
        metricToggle?.addEventListener('click', (e) => {
            const btn = e.target.closest('[data-metric]')
            if (!btn) return
            currentMetric = btn.dataset.metric
            setActiveBtn(metricToggle, currentMetric, 'data-metric')
            chart.setOption(buildChartOption(chartData, currentMetric))
        })
    }

    function switchScope(scope) {
        currentScope = scope
        const d = scopeData[scope]
        if (!d) return

        const scopeToggle = document.getElementById('stats-scope-toggle')
        if (scopeToggle) setActiveBtn(scopeToggle, currentScope, 'data-scope')

        if (d.stat_cards?.length) renderCards(d.stat_cards)
        renderMimeTable(d.types)

        const updatedEl = document.getElementById('stats-page-updated')
        if (updatedEl) {
            if (scope === 'mine' && d.updated_at) {
                updatedEl.textContent = `Updated: ${d.updated_at}`
                updatedEl.classList.remove('d-none')
            } else {
                updatedEl.classList.add('d-none')
            }
        }

        const chartWrap = document.getElementById('stats-chart-wrap')
        if (d.chart) {
            chartWrap?.classList.remove('d-none')
            chartData = d.chart
            if (chart)
                chart.setOption(buildChartOption(chartData, currentMetric))
        } else {
            chartWrap?.classList.add('d-none')
        }
    }

    Promise.all([
        fetchStatsJson(statsUrl),
        serverStatsUrl ? fetchStatsJson(serverStatsUrl) : Promise.resolve(null),
    ])
        .then(([data, serverData]) => {
            scopeData.mine = data
            if (serverData) scopeData.server = serverData

            document
                .getElementById('stats-page-loading')
                ?.classList.add('d-none')

            const active = scopeData[currentScope]
            const hasStats =
                currentScope === 'mine'
                    ? data.has_stats
                    : active?.stat_cards?.length > 0

            if (!hasStats) {
                document
                    .getElementById('stats-page-no-stats')
                    ?.classList.remove('d-none')
                return
            }

            document
                .getElementById('stats-page-content')
                ?.classList.remove('d-none')

            const scopeToggle = document.getElementById('stats-scope-toggle')
            if (scopeToggle && serverData) {
                scopeToggle.classList.remove('d-none')
                setActiveBtn(scopeToggle, currentScope, 'data-scope')
                scopeToggle.addEventListener('click', (e) => {
                    const btn = e.target.closest('[data-scope]')
                    if (!btn) return
                    switchScope(btn.dataset.scope)
                })
            }

            if (active?.stat_cards?.length) renderCards(active.stat_cards)
            renderMimeTable(active?.types)

            if (currentScope === 'mine' && data.updated_at) {
                const el = document.getElementById('stats-page-updated')
                if (el) {
                    el.textContent = `Updated: ${data.updated_at}`
                    el.classList.remove('d-none')
                }
            }

            if (active?.chart) {
                chartData = active.chart
                if (typeof echarts !== 'undefined') initChart()
            } else {
                document
                    .getElementById('stats-chart-wrap')
                    ?.classList.add('d-none')
            }
        })
        .catch(() => {
            document.getElementById('stats-page-loading')?.remove()
            document
                .getElementById('stats-page-error')
                ?.classList.remove('d-none')
        })

    document.addEventListener('stats:reload', () => {
        setTimeout(() => {
            Promise.all([
                fetchStatsJson(statsUrl),
                serverStatsUrl
                    ? fetchStatsJson(serverStatsUrl)
                    : Promise.resolve(null),
            ])
                .then(([data, serverData]) => {
                    scopeData.mine = data
                    if (serverData) scopeData.server = serverData
                    switchScope(currentScope)
                })
                .catch(() => {})
        }, 3000)
    })
})()
