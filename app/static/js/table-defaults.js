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
    render: DataTable.render.select(),
    width: '32px',
    responsivePriority: 2,
    className: 'dt-select-col',
    defaultContent: '',
}
export const selectConfig = {
    style: 'multi',
    selector: 'td:first-child',
}

export const paginatedTableDefaults = {
    paging: false,
    order: [0, 'desc'],
    responsive: true,
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
