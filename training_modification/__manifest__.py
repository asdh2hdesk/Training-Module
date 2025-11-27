{
    'name': 'Training',
    'version': '18.0.1.0',
    'category': 'Website',
    'summary': 'Training Module',
    'description': """""",
    'author': 'Megha',
    'price': 0,
    'license': 'LGPL-3',
    'currency': "INR",
    'depends': ['base', 'website_slides', 'hr', 'mass_mailing'],
    'data': [
            'data/menu.xml',
            # 'security/training_security.xml',
            'security/ir.model.access.csv',
            # 'data/tni_sequence.xml',
            'views/training_views.xml',
            'views/mail.xml',
            'views/main_menu.xml',
            'views/attendance_proof_templates.xml',
            # 'views/training_plan_views.xml',
            # 'views/training_batch_views.xml',
            # 'views/training_schedule_views.xml',
            # 'views/menu_views.xml',
            # 'views/tni.xml'

        ],
    'assets': {
            'web.assets_backend': [
                'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js',
                'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css',
                'training_modification/static/src/css/elearning_dashboard.css',
                'training_modification/static/src/js/elearning_dashboard.js',

                'training_modification/static/src/xml/dashboard_template.xml',
            ],
        },
    'installable': True,
    'auto_install': False,
    'application': True,
}
