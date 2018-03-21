
/***
 * The Settings Panel is managed with AngularJS.
 * Following is the AngularJS Application and Controller.
 * Our $scope is initialized with a $http request that retrieves a JSON like that:
 * {
 * 	"boolean": [
 * 		"key",
 * 		...
 * 	],
 * 	"defaults": {
 * 		"key1": "default",
 * 		"key2": false,
 * 		"key3": [
 * 			4,
 * 			2,
 * 		],
 * 		...
 * 	},
 * 	"integer": [
 * 		"key",
 * 	],
 * 	"multi": [
 * 		"key",
 * 	],
 * 	"placeholders": {
 * 		"key": "placeholder",
 * 		...
 * 	},
 * 	"results": {
 * 		"boolean": [
 * 			{
 * 				"name": "key",
 * 				"value": true
 * 			},
 * 			...
 * 		],
 * 		"clients": [
 * 			{
 * 				"name": "clientname",
 * 				"value": "/etc/burp/clientconfdir/clientname"
 * 			},
 * 			...
 * 		],
 * 		"common": [
 * 			{
 * 				"name": "key",
 * 				"value": "val"
 * 			},
 * 			...
 * 		],
 * 		"integer": [
 * 			{
 * 				"name": "key",
 * 				"value": 42
 * 			},
 * 			...
 * 		],
 * 		"multi": [
 * 			{
 * 				"name": "key",
 * 				"value": [
 * 					"value1",
 * 					"value2",
 * 					...
 * 				]
 * 			},
 * 			...
 * 		],
 *    "includes": [
 *      "glob",
 *      "example*.conf",
 *      ...
 *    ],
 *    "includes_ext": [
 *      "glob",
 *      "example1.conf",
 *      "example_toto.conf",
 *      ...
 *    ]
 * 	},
 * 	"server_doc": {
 * 		"key": "documentations of the specified key from the manpage",
 * 		...
 * 	},
 * 	"string": [
 * 		"key",
 * 		...
 * 	],
 * 	"suggest": {
 * 		"key": [
 * 			"value1",
 * 			"value2",
 * 		],
 * 		[...]
 * 	}
 * }
 * The JSON is then split-ed out into several dict/arrays to build our form.
 */
{% import 'macros.html' as macros %}

var _cache_id = _EXTRA;

var _me = undefined;
var _users = {};
var _auth_backends = {};
var _users_array = [];
var __promises = [];
var __globals_promises = [];

var app = angular.module('MainApp', ['ngSanitize', 'ui.select', 'mgcrea.ngStrap', 'datatables']);

app.config(function(uiSelectConfig) {
	uiSelectConfig.theme = 'bootstrap';
});

app.controller('AdminCtrl', ['$scope', '$http', '$scrollspy', 'DTOptionsBuilder', 'DTColumnDefBuilder', function($scope, $http, $scrollspy, DTOptionsBuilder, DTColumnDefBuilder) {
	var vm = this;
	$scope.auth_backends = [];

  $http.get('{{ url_for("api.auth_backends") }}', { headers: { 'X-From-UI': true } })
		.then(function (response) {
			$scope.auth_backends = [];
			_auth_backends = {};
			angular.forEach(response.data, function(back, i) {
				_auth_backends[back.name] = back;
				$scope.auth_backends.push(back);
			});
			$scope.auth_backend = "placeholder";
			vm.userAdd.auth_backend.$setValidity('valid', false);
			vm.userAdd.$setPristine();
		});

	$scope.checkSelect = function() {
		vm.userAdd.auth_backend.$setValidity('valid', ($scope.auth_backend != "placeholder"));
	};

	$scope.addUser = function(e) {
		e.preventDefault();
		var form = $(e.target);
		submit = form.find('button[type="submit"]');
		sav = submit.html();
		submit.html('<i class="fa fa-fw fa-spinner fa-pulse" aria-hidden="true"></i>&nbsp;{{ _("Creating...") }}');
		submit.attr('disabled', true);
		$http({
			url: form.attr('action'),
			method: form.attr('method'),
			params: {
				username: $scope.auth_username,
				password: $scope.auth_password,
				backend: $scope.auth_backend,
			},
			headers: { 'X-From-UI': true },
		})
		.catch(myFail)
		.then(function(response) {
			notifAll(response.data);
			$scope.auth_username = null;
			$scope.auth_password = null;
			$scope.auth_backend = "placeholder";
			vm.userAdd.auth_backend.$setValidity('valid', false);
			vm.userAdd.auth_username.$setUntouched();
			vm.userAdd.auth_password.$setUntouched();
			vm.userAdd.auth_password.$setPristine();
			vm.userAdd.$setPristine();
			_authentication();
		})
		.finally(function() {
			submit.html(sav);
			submit.attr('disabled', false);
		});
	};
}]);

var _users_table = $('#table-users').DataTable( {
	{{ macros.translate_datatable() }}
	{{ macros.get_page_length() }}
	responsive: true,
	processing: true,
	fixedHeader: true,
	select: {
		style: 'os',
	},
	data: [],
	rowId: 'id',
	rowCallback: function( row, data, index ) {
		var classes = row.className.split(' ');
		_.each(classes, function(cl) {
			if (_.indexOf(['odd', 'even'], cl) != -1) {
				row.className = cl;
				return;
			}
		});
		_.each(data.raw, function(raw) {
			if (raw.name === _me.name && raw.backend == _me.backend) {
				row.className += ' success';
				return;
			}
		});
	},
	columns: [
		{
			data: null,
			render: function ( data, type, row ) {
				return data.id;
			}
		},
		{
			data: null,
			render: function ( data, type, row ) {
				var ret = '';
				$.each(data.backends, function(i, back) {
					ret += '<span class="label label-default">'+back+'</span>&nbsp;';
				});
				return ret;
			}
		},
		{
			data: null,
			render: function ( data, type, row ) {
				var ret = '';
				$.each(data.roles, function(i, role) {
					ret += '<span class="label label-warning">'+role+'</span>&nbsp;';
				});
				return ret;
			}
		},
		{
			data: null,
			render: function ( data, type, row ) {
				var ret = '';
				$.each(data.groups, function(i, group) {
					ret += '<span class="label label-primary">'+group+'</span>&nbsp;';
				});
				return ret;
			}
		},
		{
			data: null,
			render: function ( data, type, row ) {
				return '<button data-member="'+data.id+'" class="btn btn-xs btn-danger btn-delete-user" title="{{ _("Remove") }}"><i class="fa fa-trash" aria-hidden="true"></i></button>&nbsp;<button data-member="'+data.id+'" class="btn btn-xs btn-info btn-edit-user" title="{{ _("Edit") }}"><i class="fa fa-pencil" aria-hidden="true"></i></button>&nbsp;<button data-member="'+data.id+'" class="btn btn-xs btn-warning btn-sessions-user" title="{{ _("Sessions") }}"><i class="fa fa-list-alt" aria-hidden="true"></i></button>';
			}
		},
	],
});

var g = $.getJSON('{{ url_for("api.admin_me") }}').done(function (data) {
	_me = data;
});
__globals_promises.push(g);

var _authentication = function() {
	$('#waiting-user-container').show();
	$('#table-users-container').hide();
	var __usernames = [];
	$.getJSON('{{ url_for("api.auth_users") }}').done(function (users) {
		__promises = [];
		$.each(users, function(i, user) {
			__usernames.push(user.name);
			if (_users[user.name]) {
				if (_users[user.name]['backends'].indexOf(user.backend) === -1) {
					_users[user.name]['backends'].push(user.backend);
				}
				if (_users[user.name]['raw'].indexOf(user) === -1) {
					_users[user.name]['raw'].push(user);
				}
			} else {
				_users[user.name] = {
					id: user.name,
					backends: [user.backend],
					roles: [],
					groups: [],
					raw: [user],
				};
				var p = $.getJSON('{{ url_for("api.acl_groups_of", member="") }}'+user.name).done(function (data) {
					_users[user.name]['groups'] = data.groups;
				});
				__promises.push(p);
				p = $.getJSON('{{ url_for("api.acl_is_admin", member="") }}'+user.name).done(function (data) {
					if (data.admin) {
						_users[user.name]['roles'].push('admin');
					}
				});
				__promises.push(p);
				p = $.getJSON('{{ url_for("api.acl_is_moderator", member="") }}'+user.name).done(function (data) {
					if (data.moderator) {
						_users[user.name]['roles'].push('moderator');
					}
				});
				__promises.push(p);
			}
		});
		var redraw = false;
		_users_array = [];
		$.each(_users, function(key, value) {
			if (__usernames.indexOf(key) == -1) {
				delete _users[key];
				redraw = true;
			} else {
				_users_array.push(value);
			}
		});
		if (redraw) {
			_users_table.clear();
			_users_table.rows.add(_users_array).draw();
			$('#waiting-user-container').hide();
			$('#table-users-container').show();
		}
		$.when.apply( $, __promises ).done(function() {
			_users_array = [];
			$.each(_users, function(key, value) {
				_users_array.push(value);
			});
			_users_table.clear();
			_users_table.rows.add(_users_array).draw();
			$('#waiting-user-container').hide();
			$('#table-users-container').show();
		});
	});
};

var _admin = function() {
	_authentication();
};

{{ macros.page_length('#table-list-clients') }}
{{ macros.page_length('#table-list-templates') }}

$( document ).ready(function () {
	$('#config-nav a').click(function (e) {
		e.preventDefault();
		$(this).tab('show');
	});
});

/* Delete user */
var _remove_selected = 0;
$( document ).on('click', '.btn-delete-user', function(e) {
	var user_id = $(this).data('member');
	var user = _users[user_id];
	var content = '<legend>{{ _("Please select the backend(s) from which to remove the user:") }}</legend>';
	$.each(user['backends'], function(i, back) {
		var disabled_legend = '{{ _("The backend does not support user removal") }}';
		var disabled = 'disabled title="'+disabled_legend+'"';
		var is_enabled = _auth_backends[back]['del'];
		content += '<div class="checkbox"><label><input type="checkbox" name="user_backend" data-id="'+user_id+'" data-backend="'+back+'" '+(is_enabled?'':disabled)+'>'+back+(is_enabled?'':' <em>('+disabled_legend+')</em>')+'</label></div>';
	});
	/* disable submit button while we did not select a backend */
	$('#perform-delete').prop('disabled', true);
	$('#delete-details').html(content);
	$('#delete-user-modal').modal('toggle');
});
$( document ).on('change', 'input[name=user_backend]', function(e) {
	var user_id = $(this).data('id');
	var backend = $(this).data('backend');
	if (user_id == _me.id && backend == _me.backend) {
		if ($(this).is(':checked')) {
			$('#delete-confirm').show();
		} else {
			$('#delete-confirm').hide();
		}
	}
	if ($(this).is(':checked')) {
		_remove_selected++;
	} else {
		_remove_selected--;
	}
	if (_remove_selected > 0) {
		$('#perform-delete').prop('disabled', false);
	} else {
		$('#perform-delete').prop('disabled', true);
	}
});
$('#perform-delete').on('click', function(e) {
	$.each($('input[name=user_backend]'), function(i, elmt) {
		var e = $(elmt);
		if (e.is(':checked')) {
			$.ajax({
				url: "{{ url_for('api.auth_users', name='') }}"+$(e).data('id')+"?backend="+$(e).data('backend'),
				type: 'DELETE',
				headers: { 'X-From-UI': true },
			}).done(function(data) {
				notifAll(data);
				_authentication();
			}).fail(myFail);
		}
	});
});

/* Edit user */
$( document ).on('click', '.btn-edit-user', function(e) {
	var user_id = $(this).data('member');
	var user = _users[user_id];
	var content = '<legend>{{ _("Please select the backend from which to edit the user from:") }}</legend>';
	content += '<div class="form-group"><label for="edit_backend" class="col-lg-2 control-label">Backend</label>';
	content += '<div class="col-lg-10"><select class="form-control" id="edit_backend" name="edit_backend" data-id="'+user_id+'"><option disabled selected value="placeholder">'+'{{ _("Please select a backend") }}'+'</option>';
	$.each(user['backends'], function(i, back) {
		is_enabled = _auth_backends[back]['mod'];
		content += '<option'+(is_enabled?'':' disabled')+'>'+back+'</option>';
	});
	content += '</select></div></div>';
	$('#perform-edit').prop('disabled', true);
	$('#edit-details').html(content);
	$('#edit-user-modal').modal('toggle');
});
$( document ).on('change', '#edit_backend', function(e) {
	if ($('#edit_backend option:selected').val() != 'placeholder') {
		$('#perform-edit').prop('disabled', false);
	}
});
$('#perform-edit').on('click', function(e) {
	location = "{{ url_for('view.admin_authentication', user='') }}"+$('#edit_backend').data('id')+'?backend='+$('#edit_backend option:selected').text();
});

/* Add user */


/* user sessions */
$( document ).on('click', '.btn-sessions-user', function(e) {
	var user_id = $(this).data('member');
	location = "{{ url_for('view.admin_sessions', user='') }}"+user_id;
});
