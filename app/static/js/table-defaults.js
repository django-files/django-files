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
