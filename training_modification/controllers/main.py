from odoo import http
from odoo.http import request
import base64


class AttendanceProofController(http.Controller):

    @http.route('/slides/course/<int:channel_id>/upload-proof', type='http', auth='user', website=True)
    def upload_proof_page(self, channel_id, **kwargs):
        """Page to upload attendance proof"""
        channel = request.env['slide.channel'].sudo().browse(channel_id)

        # Check if channel exists
        if not channel.exists():
            return request.redirect('/slides')

        partner = request.env.user.partner_id

        # Check if user is enrolled in the course
        is_member = request.env['slide.channel.partner'].search([
            ('channel_id', '=', channel_id),
            ('partner_id', '=', partner.id)
        ], limit=1)

        if not is_member:
            return request.redirect(f'/slides/{channel_id}')

        # Get all training schedules for this course
        training_schedules = request.env['training.calendar'].search([
            ('course_id', '=', channel_id)
        ], order='training_date desc')

        # Get all uploaded proofs for this user and course
        existing_proofs = request.env['attendance.proof'].search([
            ('partner_id', '=', partner.id),
            ('course_id', '=', channel_id)
        ], order='upload_date desc')

        # Get training dates that already have proofs
        uploaded_training_dates = existing_proofs.mapped('training_date')

        # Get success and error messages from session
        success_message = request.session.pop('proof_upload_success', False)
        error_message = request.session.pop('proof_upload_error', False)

        # Prepare render values with main object for website editor
        values = {
            'channel': channel,
            'training_schedules': training_schedules,
            'existing_proofs': existing_proofs,
            'uploaded_training_dates': uploaded_training_dates,
            'success_message': success_message,
            'error_message': error_message,
            'main_object': channel,  # For website editor
            'editable': True,
        }

        return request.render('training_modification.attendance_proof_upload_page', values)

    @http.route('/slides/course/<int:channel_id>/submit-proof', type='http', auth='user', methods=['POST'],
                website=True, csrf=True)
    def submit_proof(self, channel_id, training_date=None, proof_file=None, notes=None, **kwargs):
        """Handle proof submission - supports multiple files"""
        from datetime import datetime

        partner = request.env.user.partner_id

        # Validate training date is provided
        if not training_date:
            request.session['proof_upload_error'] = 'Please select a training schedule.'
            return request.redirect(f'/slides/course/{channel_id}/upload-proof')

        # Verify training schedule exists
        training_schedule = request.env['training.calendar'].search([
            ('course_id', '=', channel_id),
            ('training_date', '=', training_date)
        ], limit=1)

        if not training_schedule:
            request.session['proof_upload_error'] = 'Invalid training schedule selected.'
            return request.redirect(f'/slides/course/{channel_id}/upload-proof')

        # Check if training has already started
        current_datetime = datetime.now()
        training_datetime = datetime.combine(training_schedule.training_date, datetime.min.time())

        if training_schedule.start_time:
            hours = int(training_schedule.start_time)
            minutes = int((training_schedule.start_time % 1) * 60)
            training_datetime = training_datetime.replace(hour=hours, minute=minutes)

        if training_datetime > current_datetime:
            request.session['proof_upload_error'] = 'Cannot upload proof before the training session starts.'
            return request.redirect(f'/slides/course/{channel_id}/upload-proof')

        # Check if proof already exists for this training date
        existing_proof = request.env['attendance.proof'].search([
            ('partner_id', '=', partner.id),
            ('course_id', '=', channel_id),
            ('training_date', '=', training_date)
        ], limit=1)

        if existing_proof:
            request.session['proof_upload_error'] = 'You have already uploaded proof for this training schedule.'
            return request.redirect(f'/slides/course/{channel_id}/upload-proof')

        # Verify training schedule exists
        training_schedule = request.env['training.calendar'].search([
            ('course_id', '=', channel_id),
            ('training_date', '=', training_date)
        ], limit=1)

        if not training_schedule:
            request.session['proof_upload_error'] = 'Invalid training schedule selected.'
            return request.redirect(f'/slides/course/{channel_id}/upload-proof')

        # Handle multiple file uploads
        files = request.httprequest.files.getlist('proof_file')

        if files:
            try:
                for proof_file in files:
                    if proof_file:
                        vals = {
                            'partner_id': partner.id,
                            'course_id': channel_id,
                            'training_date': training_date,
                            'proof_image': base64.b64encode(proof_file.read()),
                            'proof_filename': proof_file.filename,
                            'notes': notes or '',
                            'status': 'pending'
                        }
                        request.env['attendance.proof'].create(vals)

                # Set success message
                request.session['proof_upload_success'] = True

            except Exception as e:
                # Log error
                request.env['ir.logging'].sudo().create({
                    'name': 'Proof Upload Error',
                    'type': 'server',
                    'level': 'error',
                    'message': str(e),
                    'path': 'attendance.proof',
                    'line': '0',
                    'func': 'submit_proof'
                })
                request.session['proof_upload_error'] = 'An error occurred while uploading. Please try again.'
        else:
            request.session['proof_upload_error'] = 'Please select at least one file to upload.'

        return request.redirect(f'/slides/course/{channel_id}/upload-proof')

    @http.route('/slides/course/proof/delete/<int:proof_id>', type='http', auth='user', website=True, csrf=True)
    def delete_proof(self, proof_id, **kwargs):
        """Delete a proof record"""
        partner = request.env.user.partner_id
        proof = request.env['attendance.proof'].search([
            ('id', '=', proof_id),
            ('partner_id', '=', partner.id)
        ], limit=1)

        if proof:
            channel_id = proof.course_id.id
            proof.unlink()
            return request.redirect(f'/slides/course/{channel_id}/upload-proof')

        return request.redirect('/slides')

    @http.route('/slides/course/<int:channel_id>/calendar', type='http', auth='user', website=True)
    def training_calendar(self, channel_id, month=None, year=None, **kwargs):
        """Display training calendar for a course with color-coded status"""
        import calendar
        from datetime import datetime, date, timedelta

        channel = request.env['slide.channel'].sudo().browse(channel_id)

        if not channel.exists():
            return request.redirect('/slides')

        # Get current user partner
        current_partner = request.env.user.partner_id

        # Get current month/year or use provided
        today = date.today()
        current_month = int(month) if month else today.month
        current_year = int(year) if year else today.year

        # Calculate previous and next month
        if current_month == 1:
            prev_month, prev_year = 12, current_year - 1
        else:
            prev_month, prev_year = current_month - 1, current_year

        if current_month == 12:
            next_month, next_year = 1, current_year + 1
        else:
            next_month, next_year = current_month + 1, current_year

        # Get month calendar
        cal = calendar.monthcalendar(current_year, current_month)
        month_name = calendar.month_name[current_month]

        # Get training dates for this month
        start_date = date(current_year, current_month, 1)
        if current_month == 12:
            end_date = date(current_year + 1, 1, 1)
        else:
            end_date = date(current_year, current_month + 1, 1)

        trainings = request.env['training.calendar'].search([
            ('course_id', '=', channel_id),
            ('training_date', '>=', start_date),
            ('training_date', '<', end_date)
        ])

        # Build training dictionary with status
        training_dict = {}
        for training in trainings:
            # Check if proof exists for this date and user
            proof_exists = request.env['attendance.proof'].search_count([
                ('partner_id', '=', current_partner.id),
                ('course_id', '=', channel_id),
                ('training_date', '=', training.training_date)
            ]) > 0

            # Determine status color

            current_datetime = datetime.now()
            training_datetime = datetime.combine(training.training_date, datetime.min.time())

            # Add training start time if available
            if training.start_time:
                hours = int(training.start_time)
                minutes = int((training.start_time % 1) * 60)
                training_datetime = training_datetime.replace(hour=hours, minute=minutes)
            if training_datetime > current_datetime:
                status_color = 'warning'  # Yellow - upcoming/scheduled
            elif proof_exists:
                status_color = 'success'  # Green - proof attached
            else:
                status_color = 'danger'  # Red - past date, no proof

            training_dict[training.training_date.day] = {
                'training': training,
                'status_color': status_color,
                'proof_exists': proof_exists,
            }

        # Build calendar weeks
        calendar_weeks = []
        for week in cal:
            week_days = []
            for day in week:
                day_data = {'day': day if day != 0 else ''}
                if day != 0:
                    day_date = date(current_year, current_month, day)
                    day_data['is_today'] = day_date == today
                    if day in training_dict:
                        day_data['has_training'] = True
                        day_data['training'] = training_dict[day]['training']
                        day_data['status_color'] = training_dict[day]['status_color']
                        day_data['proof_exists'] = training_dict[day]['proof_exists']
                week_days.append(day_data)
            calendar_weeks.append(week_days)

        # Get upcoming trainings
        upcoming_trainings = request.env['training.calendar'].search([
            ('course_id', '=', channel_id),
            ('training_date', '>=', today)
        ], limit=5, order='training_date asc')

        # Prepare render values with main object for website editor
        values = {
            'channel': channel,
            'calendar_weeks': calendar_weeks,
            'month_name': month_name,
            'year': current_year,
            'prev_month': prev_month,
            'prev_year': prev_year,
            'next_month': next_month,
            'next_year': next_year,
            'upcoming_trainings': upcoming_trainings,
            'main_object': channel,  # For website editor
            'editable': True,
        }

        return request.render('training_modification.training_calendar_page', values)