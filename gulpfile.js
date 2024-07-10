const gulp = require('gulp')
const download = require('gulp-download2')
// const copy = require('gulp-copy')
// const concat = require('gulp-concat')

gulp.task('animate', () => {
    return gulp
        .src('node_modules/animate.css/animate.min.css')
        .pipe(gulp.dest('app/static/dist/animate'))
})

gulp.task('bootstrap', () => {
    return gulp
        .src([
            'node_modules/bootstrap/dist/css/bootstrap.min.css',
            'node_modules/bootstrap/dist/js/bootstrap.bundle.min.js',
        ])
        .pipe(gulp.dest('app/static/dist/bootstrap'))
})

gulp.task('clipboard', () => {
    return gulp
        .src('node_modules/clipboard/dist/clipboard.min.js')
        .pipe(gulp.dest('app/static/dist/clipboard'))
})

gulp.task('datatables', () => {
    return gulp
        .src([
            'node_modules/datatables.net/js/dataTables.min.js',
            'node_modules/datatables.net-bs5/js/dataTables.bootstrap5.min.js',
            'node_modules/datatables.net-bs5/css/dataTables.bootstrap5.min.css',
            'node_modules/datatables.net-datetime/dist/dataTables.dateTime.min.js',
            'node_modules/datatables.net-plugins/dataRender/datetime.min.js',
            'node_modules/datatables.net-plugins/sorting/file-size.min.js',
            'node_modules/datatables.net-responsive/js/dataTables.responsive.min.js',
        ])
        .pipe(gulp.dest('app/static/dist/datatables'))
})

gulp.task('fontawesome', () => {
    return gulp
        .src(
            [
                'node_modules/@fortawesome/fontawesome-free/css/all.min.css',
                'node_modules/@fortawesome/fontawesome-free/js/all.min.js',
                'node_modules/@fortawesome/fontawesome-free/webfonts/**/*',
            ],
            { base: 'node_modules/@fortawesome/fontawesome-free' }
        )
        .pipe(gulp.dest('app/static/dist/fontawesome'))
})

gulp.task('js-cookie', () => {
    return gulp
        .src('node_modules/js-cookie/dist/js.cookie.min.js')
        .pipe(gulp.dest('app/static/dist/js-cookie'))
})

gulp.task('jquery', () => {
    return gulp
        .src('node_modules/jquery/dist/jquery.min.js')
        .pipe(gulp.dest('app/static/dist/jquery'))
})

gulp.task('moment', () => {
    return gulp
        .src(['node_modules/moment/min/moment.min.js'])
        .pipe(gulp.dest('app/static/dist/moment'))
})

gulp.task('swagger-ui', () => {
    return gulp
        .src([
            'node_modules/swagger-ui/dist/swagger-ui.css',
            'node_modules/swagger-ui/dist/swagger-ui-bundle.js',
            'node_modules/swagger-ui/dist/swagger-ui-standalone-preset.js',
        ])
        .pipe(gulp.dest('app/static/dist/swagger-ui'))
})

gulp.task('uppy', () => {
    return download([
        'https://releases.transloadit.com/uppy/v3.27.0/uppy.min.mjs',
        'https://releases.transloadit.com/uppy/v3.27.0/uppy.min.css',
    ]).pipe(gulp.dest('app/static/dist/uppy'))
})

gulp.task('swagger-yaml', () => {
    return gulp.src(['swagger.yaml']).pipe(gulp.dest('app/static/dist/'))
})

gulp.task(
    'default',
    gulp.parallel(
        'animate',
        'bootstrap',
        'clipboard',
        'datatables',
        'fontawesome',
        'js-cookie',
        'jquery',
        'moment',
        'swagger-ui',
        'swagger-yaml',
        'uppy'
    )
)
