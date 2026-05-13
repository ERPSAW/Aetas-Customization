frappe.ui.form.on('AOT Dashboard Config', {
	refresh: function (frm) {
		frm.add_custom_button(__('Download Excel'), function () {
			const url = frappe.urllib.get_full_url(
				'/api/method/aetas_customization.aetas_customization.aot_data.download_excel'
			);
			const a = document.createElement('a');
			a.href = url;
			a.download = '';
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
		}, __('Actions'));

		frm.add_custom_button(__('Send Test Email'), function () {
			frappe.prompt(
				[{ label: 'Recipient Email', fieldname: 'email', fieldtype: 'Data', options: 'Email', reqd: 1 }],
				function (values) {
					frappe.show_alert({ message: __('Sending...'), indicator: 'blue' });
					frappe.call({
						method: 'aetas_customization.aetas_customization.aot_data.send_test_email',
						args: { recipient: values.email },
						callback: function (r) {
							frappe.show_alert({
								message: __('Test email sent to {0}', [values.email]),
								indicator: 'green',
							});
						},
						error: function (err) {
							frappe.msgprint({ title: __('Email Failed'), message: err.message, indicator: 'red' });
						},
					});
				},
				__('Send Test Email'),
				__('Send')
			);
		}, __('Actions'));
	},
});
