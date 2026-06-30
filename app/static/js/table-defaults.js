// Shared DataTables layout presets.
// `topEnd` is where DataTables 2.x renders its built-in search input — null it
// when our shared toolbar provides search. Null every slot when the table has
// no surrounding chrome (e.g. the home dashboard cards).
export const noChromeLayout = {
    topStart: null,
    topEnd: null,
    bottomStart: null,
    bottomEnd: null,
}

export const toolbarOnlyLayout = {
    topStart: null,
    topEnd: null,
}

// Shared multi-select column. Place `selectColumn` at index 0 of `columns`,
// `selectColumnDef` at index 0 of `columnDefs`, and spread `selectConfig` into
// the top-level DataTables options as `select`. Templates need a matching
// empty `<th></th>` at the start of <thead>. CSS class `dt-select-col` keeps
// the checkbox horizontally centered (see table.css).
export const selectColumn = { data: null }
export const selectColumnDef = {
    targets: 0,
    orderable: true,
    get render() {
        return DataTable.render.select()
    },
    width: '32px',
    responsivePriority: 2,
    className: 'dt-select-col',
    defaultContent: '',
}
export const selectConfig = {
    style: 'multi',
    selector: 'td:first-child',
}

// Generic toolbar popup button wired to a <template> via Bootstrap Popover.
// onShown(body, popover) fires each open with the live popover body for event wiring.
// prepareContent(clone) fires on each open with the DocumentFragment before insertion,
// useful for syncing active states onto the clone before it's displayed.
export function initPopupBtn(btnId, tplId, onShown, { prepareContent } = {}) {
    const btn = document.getElementById(btnId)
    const tpl = document.getElementById(tplId)
    if (!btn || !tpl) return

    const popoverClass = `${btnId}-popover`
    const popover = new bootstrap.Popover(btn, {
        html: true,
        content: () => {
            const clone = tpl.content.cloneNode(true)
            prepareContent?.(clone)
            return clone
        },
        trigger: 'click',
        placement: 'bottom',
        customClass: `${popoverClass} toolbar-glass-popover`,
        popperConfig: { strategy: 'fixed' },
    })

    btn.addEventListener('shown.bs.popover', () => {
        const body = document.querySelector(`.${popoverClass} .popover-body`)
        if (!body) return
        onShown?.(body, popover)
        const onOutside = (e) => {
            if (
                !btn.contains(e.target) &&
                !body.closest('.popover')?.contains(e.target)
            )
                popover.hide()
        }
        document.addEventListener('click', onOutside)
        btn.addEventListener(
            'hidden.bs.popover',
            () => document.removeEventListener('click', onOutside),
            { once: true }
        )
    })
}

// Toggle the active state and label of a toolbar popup button.
// Pass null/undefined activeLabel to deactivate; pass a string to activate.
export function syncPopupBtnActive(
    btnId,
    activeLabel,
    defaultLabel = 'Filter'
) {
    const btn = document.getElementById(btnId)
    if (!btn) return
    const span = btn.querySelector('.files-toolbar-view-label')
    btn.classList.toggle('view-active', !!activeLabel)
    if (span) span.textContent = activeLabel ?? defaultLabel
}

// Read the current ?user= URL param, resolve the display name from the popup
// template's <select> options, and sync the filter button active state.
export function syncUserFilterBtn(btnId, tplId) {
    const userId = new URL(location.href).searchParams.get('user')
    if (!userId) {
        syncPopupBtnActive(btnId, null)
        return
    }
    const tpl = document.getElementById(tplId)
    const label = tpl?.content
        .cloneNode(true)
        .querySelector(`option[value="${userId}"]`)
        ?.textContent?.trim()
    syncPopupBtnActive(btnId, label ?? 'User')
}

export const paginatedTableDefaults = {
    data: [],
    paging: false,
    order: [0, 'desc'],
    responsive: { details: false },
    saveState: true,
    searching: true,
    pageLength: -1,
    layout: toolbarOnlyLayout,
    language: {
        emptyTable: '',
        loadingRecords: '',
        zeroRecords: '',
    },
    lengthMenu: [
        [10, 25, 50, 100, 250, -1],
        [10, 25, 50, 100, 250, 'All'],
    ],
}

// Freeze DataTables' auto-width measurement during the initial bulk row insertion
// so column widths don't shift while headers are visible.  Call before adding rows.
export function dtFreezeAutoWidth(dt) {
    dt.settings()[0].oFeatures.bAutoWidth = false
}

// Re-enable auto-width, do one hidden measurement, then slide the thead in.
// Adds dt-thead-ready inside the RAF so the header is invisible throughout
// the measurement phase and animates in from its settled position.
// Also inserts a .dt-blur-strip sibling div before the DT wrapper: backdrop-filter
// doesn't work on display:table-* elements, so this non-table div provides the
// glass blur at the same sticky position as the thead (z-index 2 vs thead z-index 3).
// Call after all initial rows have been added.
export function dtRevealThead(dt) {
    const table = dt.table().node()
    const thead = table.querySelector(':scope > thead')
    thead.style.opacity = '0'
    thead.style.transform = 'translateY(-4px)'
    thead.style.transition = 'none'
    dt.settings()[0].oFeatures.bAutoWidth = true
    dt.columns.adjust()
    requestAnimationFrame(() =>
        requestAnimationFrame(() => {
            table.classList.add('dt-thead-ready')
            thead.style.opacity = ''
            thead.style.transform = ''
            thead.style.transition = ''

            const container =
                table.closest('.dt-container') ?? table.parentElement
            if (
                container &&
                !container.previousElementSibling?.classList.contains(
                    'dt-blur-strip'
                )
            ) {
                const strip = document.createElement('div')
                strip.className = 'dt-blur-strip'
                strip.setAttribute('aria-hidden', 'true')
                const updateH = (h) =>
                    strip.style.setProperty('--dt-thead-h', `${h}px`)
                updateH(thead.offsetHeight)
                container.before(strip)
                new ResizeObserver(([entry]) =>
                    updateH(entry.contentRect.height)
                ).observe(thead)
            }
        })
    )
}
