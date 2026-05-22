export const paginatedTableDefaults = {
    paging: false,
    order: [0, 'desc'],
    responsive: true,
    saveState: true,
    searching: true,
    pageLength: -1,
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
