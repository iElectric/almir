/*jslint regexp: true,
         browser: true,
         sloppy: true,
         white: true,
         plusplus: true,
         indent: 4,
         maxlen: 200 */
/*global $, jQuery, tabletools_swf, deform, datatables_route */

// Taken from: https://gist.github.com/1101534
jQuery.extend({
    parseQuerystring: function () {
        var nvpair = {},
          qs = window.location.search.replace('?', ''),
          pairs = qs.split('&');
        $.each(pairs, function (i, v) {
            var pair = v.split('=');
            nvpair[pair[0]] = pair[1];
        });
        return nvpair;
    }
});


function send_command(e, force_command) {
    var $console = $('#console'),
        $command = $('#command'),
        lines,
        bconsole_text = $command.val();

    if (e.which === 27) {
        $command.val('');
        return null;
    }

    if (!(e.which === 1 || e.which === 13)) {
        return null;
    }
    
    if (force_command !== true && !bconsole_text) {
        return null;
    }
    // clear command line to mimic console
    // TODO: does not work since typeahead will repopulate it
    $command.val('');

    $.ajax({
        url: '/console/input/',
        dataType: 'json',
        type: 'POST',
        data: {
            bconsole_command: bconsole_text
        },
        success: function (data) {
            if (data.commands) {
                $.each(data.commands, function (index, value) {
                    // prettyfy first line, which is the command
                    lines = value.split('<br />');
                    lines[0] = '<strong>&gt;&gt;&gt; ' + lines[0] + '</strong>';
                    value = lines.join('<br />');
                    $console.append($('<pre>' + value + '</pre'));
                });

                // scroll nicely to the bottom of text
                $console.animate({scrollTop: $console.prop("scrollHeight") - $console.height() }, 300);
            } 

            if (data.error) {
                $console.before($('<div class="alert alert-error"><a class="close" data-dismiss="alert">×</a>' + data.error + '</div>'));
            }
        },
        error: function () {
            $console.before($('<div class="alert alert-error"><a class="close" data-dismiss="alert">×</a>Something went wrong, inspect server logs.</div>'));
        }
    });
}

$(function () {
    var setup_datatables = function () {
        var $this = $(this),
            server_side_setup,
            /* datatables initialisation: http://datatables.net/usage/options */
            options = {
                "sDom": "<'row-fluid'<'span5'l><'span7'fT>r>t<'row-fluid'<'span6'i><'span6'p>>",
                "sPaginationType": "bootstrap",
                "oLanguage": {
                    "sLengthMenu": "_MENU_ per page"
                },
                "oTableTools": {
                    sSwfPath: tabletools_swf,
                    aButtons: ["copy", "csv", "pdf", "print"]
                },
                "iDisplayLength": 50,
                "bDestroy": true,
                "fnDrawCallback": function () {
                    /* make datatables rows clickable by provided link */
                    $this.find('tbody tr').each(function () {
                        var $this = $(this),
                            href;
                        // clickable-row
                        href = $this.find('td:first a').attr('href');
                        /*if (typeof href == 'string') {
                            $this.addClass('clickable-row').click(function (e) {
                                window.location = href;
                            });
                        }  commented out.. is not usable when there are dropboxes in the rows, we can adjust it?*/
                    });
                }
            };

        // dashboard
        if ($.inArray($this.prevAll('h2').attr('id'), ['last_jobs', 'upcoming_jobs', 'running_jobs']) !== -1) {
            options.sDom = "<'row-fluid'<'span12'fT>r>t<'row-fluid'>";
        }

        server_side_setup = function (more) {
            options.bProcessing = true;
            options.bServerSide = true;
            options.sAjaxSource = datatables_route;
            options.fnServerParams = function (aoData) {
                aoData.push({name: 'referrer', value: document.location.pathname});
                $.each($('form').serializeArray(), function (index, value) {
                    aoData.push(value);
                });
                $.each(more || [], function (index, value) {
                    aoData.push(value);
                });
            };
        };

        if ($this.attr('id') === 'job_files') {
            server_side_setup([{name: "context", value: "files"}]);
            options.aoColumns = [
                {sTitle: "Filename", mDataProp: "filename", sName: "path.path;filename.name"},
                {sTitle: "Size", mDataProp: "size", bSortable: false, bSearchable: false},
                {sTitle: "Mode", mDataProp: "mode", bSortable: false, bSearchable: false},
                {sTitle: "UID", mDataProp: "uid", bSortable: false, bSearchable: false},
                {sTitle: "GID", mDataProp: "gid", bSortable: false, bSearchable: false}
            ];
        }

        if ($this.attr('id') === 'list_logs') {
            server_side_setup();
            options.aoColumns = [
                {sTitle: "Job", mDataProp: "jobid", sWidth: "50px"},
                {sTitle: "Time", mDataProp: "time", sWidth: "100px", bSearchable: false},
                {sTitle: "Message", mDataProp: "logtext"}
            ];
            options.aaSorting = [[1, "desc"]];
        }

        if ($this.attr('id') === 'list_jobs') {
            server_side_setup();
            options.aoColumns = [
                {sTitle: "Name", mDataProp: "name", sName: "jobid"},
                {sTitle: "Status", mDataProp: "status", sName: "status.joblongstatus"},
                {sTitle: "Type", mDataProp: "type"},
                {sTitle: "Level", mDataProp: "level"},
                {sTitle: "Files", mDataProp: "jobfiles"},
                {sTitle: "Client", mDataProp: "client_name", sName: "client.clientid"},
                {sTitle: "Started", mDataProp: "starttime", aaSorting: "asc"},
                {sTitle: "Duration", mDataProp: "duration", bSortable: false, bSearchable: false},  // sqlite does not support timedate types
                {sTitle: "Errors", mDataProp: "joberrors"}
            ];
            options.aaSorting = [[6, "desc"]];
        }

        // console
        if ($this.attr('id') === "command_help") {
            options.sDom = "<'row-fluid'<'span12'f>r>t<'row-fluid'>";
            options.iDisplayLength = 200;
        }

        // default sorting order
        $this.find('thead th').each(function (index) {
            if ($.inArray($(this).text(), ['Scheduled', 'Started']) !== -1) {
                options.aaSorting = [[index, "asc"]];
            }
            if ($.inArray($(this).text(), ['Time', 'Last written']) !== -1) {
                options.aaSorting = [[index, "desc"]];
            }
        }); 

        $this.dataTable(options);
    };
    $('.datatables').each(setup_datatables);
    // apply twitter.bootstrap markup on tabletools
    $('.DTTT_button').addClass('btn');

    // -- console.pt
    if ($('#console').length === 1) {
        // calculate height of console
        var window_height = $(window).height(),
            console_offset = $('#console').offset().top,
            command_height = $('#command').parents('.row-fluid').height() + 100,
            console_height = window_height - console_offset - command_height;
        $('#console').height(console_height);

        // enable popovers
        $('#command_help tr').popover();
        $('#command').popover({
            placement: 'left',
            trigger: 'manual'
        });

        // every 100ms check command input and display help if apropriate
        setInterval(function () {
            var command = $('#command').val(),
                title;

            // when there is no input, hide popover
            if (!command) {
                $('#command').popover('hide').data('last-command', "");
                return null;
            }

            // only change popup if we have new command
            if ($('#command').data('last-command') === command) {
                return null;
            }

            // match command title to list of help commands
            title = $('#command_help tr').filter(function () {
                var current_command = $(this).find('td:first').text(),
                    rgp = new RegExp('^' + command + '$');
                return rgp.test(current_command);
            }).attr('data-content');

            // if we have a match, display popover
            if (title) {
                $('#command').attr('data-content', title)
                    .attr('data-original-title', "Parameters for " + command)
                    .popover('show').data('last-command', command);
            }
        }, 100);

        $('#command-btn').bind('click', send_command);
        $('#command').bind('keyup', send_command);

        // connect to director right away
        send_command({which: 1}, true);
    }

    // don't focus the form since we dont want
    // datetimewidget to open on page load
    deform.focusFirstInput = $.noop;
    
    // load deform javascript
    deform.load();
    
    // filter forms for datatables
    function submitForm() {
        var dt = $('.datatables');
    
        // we first refresh tables based on form input, then
        // redraw the datatables
        // TODO: this only works if one table and one form are present
        dt.each(function () {
            $(this).dataTable().fnDestroy(true);
        });
        $('.view').after('<div></div>').next().load(document.URL + " .datatables", $('form').serialize(), function () {
            $('.datatables').each(setup_datatables);
        });
    }

    // setup events for filter forms
    $('form')
        .data('timeout', null)
        .change(submitForm)  // if we chose a value from dropdown, submit instantly
        .keypress(function (event) {  // on enter, also submit instantly
            var keycode = event.keyCode || event.which;
            if (keycode === 13) {
                submitForm();
                event.preventDefault();
            }
        })
        .bind('keyup', function () {  // when typing, wait for 0.8s pause and submit form
            clearTimeout($(this).data('timeout'));
            jQuery(this).data('timeout', setTimeout(submitForm, 800));
        });
});
