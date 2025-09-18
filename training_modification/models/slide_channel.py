from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)

class SlideChannel(models.Model):
    _inherit = 'slide.channel'

    attendance_ids = fields.One2many('slide.attendance', 'channel_id', string='Attendance')

    def write(self, vals):
        """Override write to update attendance when members change"""
        result = super().write(vals)

        # If channel_partner_ids were modified, update today's attendance
        if 'channel_partner_ids' in vals:
            self._update_today_attendance()

        return result

    def _update_today_attendance(self):
        """Update today's attendance when members change"""
        today = fields.Date.today()

        for record in self:
            # Get current attendance records for today
            existing_attendance = self.env['slide.attendance'].search([
                ('channel_id', '=', record.id),
                ('date', '=', today)
            ])

            # Get current enrolled partners
            current_partner_ids = record.channel_partner_ids.ids
            existing_partner_ids = existing_attendance.mapped('name.id')

            # Remove attendance for partners no longer enrolled
            to_remove = existing_attendance.filtered(
                lambda x: x.name.id not in current_partner_ids
            )
            if to_remove:
                to_remove.unlink()

            # Add attendance for new partners
            new_partner_ids = set(current_partner_ids) - set(existing_partner_ids)
            if new_partner_ids:
                attendance_vals = []
                for partner_id in new_partner_ids:
                    attendance_vals.append({
                        'name': partner_id,
                        'channel_id': record.id,
                        'date': today,
                        'present': False
                    })

                if attendance_vals:
                    self.env['slide.attendance'].create(attendance_vals)

    def _ensure_today_attendance(self):
        """Ensure attendance records exist for today"""
        if not self.id:
            return

        today = fields.Date.today()

        # Check if attendance already exists for today
        existing_attendance = self.env['slide.attendance'].search([
            ('channel_id', '=', self.id),
            ('date', '=', today)
        ])

        existing_partner_ids = existing_attendance.mapped('name.id')
        current_partner_ids = self.channel_partner_ids.ids

        # Create attendance for partners who don't have records for today
        missing_partner_ids = set(current_partner_ids) - set(existing_partner_ids)

        if missing_partner_ids:
            attendance_vals = []
            for partner_id in missing_partner_ids:
                attendance_vals.append({
                    'name': partner_id,
                    'channel_id': self.id,
                    'date': today,
                    'present': False
                })

            if attendance_vals:
                self.env['slide.attendance'].create(attendance_vals)

    @api.model
    def read(self, fields=None, load='_classic_read'):
        """Auto-generate attendance when form is loaded"""
        result = super().read(fields, load)

        # Auto-generate attendance for today when accessing the record
        for record in self:
            record._ensure_today_attendance()

        return result

class SlideChannelPartner(models.Model):
    _inherit = 'slide.channel.partner'

    def create(self, vals_list):
        """Override create to update attendance when new members join"""
        result = super().create(vals_list)

        # Update attendance for affected channels
        channels = result.mapped('channel_id')
        for channel in channels:
            channel._update_today_attendance()

        return result

    def unlink(self):
        """Override unlink to update attendance when members leave"""
        channels = self.mapped('channel_id')
        result = super().unlink()

        # Update attendance for affected channels
        for channel in channels:
            channel._update_today_attendance()

        return result

class SlideAttendance(models.Model):
    _name = 'slide.attendance'
    _description = 'Course Attendance'

    name = fields.Many2one('slide.channel.partner', string='Employee', required=True, ondelete='cascade')
    partner_name = fields.Char(related='name.partner_id.name', string='Employee Name', readonly=True)
    channel_id = fields.Many2one('slide.channel', string='Course', required=True, ondelete='cascade')
    date = fields.Date('Date', default=fields.Date.today)
    present = fields.Boolean('Present', default=False)

    _sql_constraints = [
        ('unique_attendance', 'unique(name, channel_id, date)',
         'Attendance record already exists for this employee on this date!'),
    ]

    def unlink(self):
        """Override unlink to remove from slide.channel.partner when attendance is deleted"""

        # Store the channel partners that will be affected
        channel_partners_to_remove = []

        for record in self:
            # Check if this is the only attendance record for this partner in this channel
            other_attendance = self.env['slide.attendance'].search([
                ('name', '=', record.name.id),
                ('channel_id', '=', record.channel_id.id),
                ('id', '!=', record.id)  # Exclude current record
            ])

            _logger.info(
                f"Checking attendance for partner {record.name.partner_id.name} in channel {record.channel_id.name}")
            _logger.info(f"Other attendance records found: {len(other_attendance)}")

            # If no other attendance records, mark for removal from channel
            if not other_attendance:
                channel_partners_to_remove.append(record.name)
                _logger.info(f"Marking {record.name.partner_id.name} for removal from channel")

        # Perform the unlink operation first
        result = super().unlink()

        # Now remove from slide.channel.partner
        for channel_partner in channel_partners_to_remove:
            try:
                # Double check the record still exists before unlinking
                if channel_partner.exists():
                    _logger.info(
                        f"Removing {channel_partner.partner_id.name} from channel {channel_partner.channel_id.name}")
                    channel_partner.unlink()
                    _logger.info("Successfully removed from channel")
            except Exception as e:
                _logger.error(f"Error removing channel partner: {e}")

        return result

    # Alternative approach - remove immediately when attendance is deleted
    def unlink_and_remove_from_channel(self):
        """Custom method to remove attendance and optionally remove from channel"""
        channel_partners_to_remove = []

        for record in self:
            # Check if this partner has other attendance records in this channel
            other_attendance_count = self.env['slide.attendance'].search_count([
                ('name', '=', record.name.id),
                ('channel_id', '=', record.channel_id.id),
                ('id', '!=', record.id)
            ])

            # If this is the only attendance record, mark channel partner for removal
            if other_attendance_count == 0:
                channel_partners_to_remove.append(record.name)

        # Remove attendance records
        result = self.unlink()

        # Remove from channel
        for cp in channel_partners_to_remove:
            if cp.exists():
                cp.unlink()

        return result

    def unlink_and_refresh(self):
        self.unlink()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

class MailingMailing(models.Model):
    _inherit = 'mailing.mailing'

    attendees_ids = fields.Many2many(
        'res.partner', string='Attendees',
        relation='mailing_attendees_partner_rel',
        column1='mailing_id',
        column2='partner_id'
    )

    course_id = fields.Many2one('slide.channel', string='Course')

    def write(self, vals):
        """Override write to sync attendees with slide.channel.partner immediately."""
        result = super().write(vals)

        for record in self:
            if not record.course_id:
                continue

            # Fetch original channel partners from DB (not cached)
            existing_channel_partners = self.env['slide.channel.partner'].search([
                ('channel_id', '=', record.course_id.id)
            ])
            existing_partner_ids = set(existing_channel_partners.mapped('partner_id').ids)

            # Current attendees after write
            current_attendee_ids = set(record.attendees_ids.ids)

            # Determine removed and added attendees
            removed_partner_ids = existing_partner_ids - current_attendee_ids
            added_partner_ids = current_attendee_ids - existing_partner_ids

            # Remove partners from slide.channel.partner and schedule attendance update
            if removed_partner_ids:
                channel_partners_to_remove = existing_channel_partners.filtered(
                    lambda cp: cp.partner_id.id in removed_partner_ids
                )
                if channel_partners_to_remove:
                    _logger.info(f"Removing partners {removed_partner_ids} from course {record.course_id.name}")
                    channel_partners_to_remove.unlink()
                    # Attendance will be updated automatically via post-commit hook in SlideChannelPartner.unlink()

            # Add new partners to slide.channel.partner
            if added_partner_ids:
                channel_partner_vals = [{
                    'channel_id': record.course_id.id,
                    'partner_id': pid
                } for pid in added_partner_ids]
                if channel_partner_vals:
                    self.env['slide.channel.partner'].create(channel_partner_vals)
                    _logger.info(f"Added new partners {added_partner_ids} to course {record.course_id.name}")

        return result

    def _remove_partners_from_course(self, course_id, partner_ids):
        """Remove partners from slide.channel.partner (attendance cascades automatically)"""
        _logger.info(f"Removing partners {partner_ids} from course {course_id}")

        channel_partners = self.env['slide.channel.partner'].search([
            ('channel_id', '=', course_id),
            ('partner_id', 'in', list(partner_ids))
        ])

        if channel_partners:
            try:
                _logger.info(f"Found {len(channel_partners)} channel partner records to remove: {channel_partners.mapped('partner_id.name')}")
                # Unlink channel partners
                channel_partners.unlink()
                # Force flush and invalidate cache to ensure changes are visible
                self.env.flush_all()
                self.env.invalidate_all()
                _logger.info("Successfully removed channel partners and flushed environment")
            except Exception as e:
                _logger.error(f"Error removing channel partners: {e}")
        else:
            _logger.info("No channel partner records found to remove")

    def _add_partners_to_course(self, course_id, partner_ids):
        """Add partners to slide.channel.partner"""
        _logger.info(f"Adding partners {partner_ids} to course {course_id}")

        # Check which partners are not already enrolled
        existing_partners = self.env['slide.channel.partner'].search([
            ('channel_id', '=', course_id),
            ('partner_id', 'in', list(partner_ids))
        ])

        already_enrolled_ids = set(existing_partners.mapped('partner_id').ids)
        new_enrollment_ids = partner_ids - already_enrolled_ids

        if new_enrollment_ids:
            # Create new slide.channel.partner records
            channel_partner_vals = []
            for partner_id in new_enrollment_ids:
                channel_partner_vals.append({
                    'channel_id': course_id,
                    'partner_id': partner_id,
                })

            if channel_partner_vals:
                new_records = self.env['slide.channel.partner'].create(channel_partner_vals)
                _logger.info(f"Created {len(new_records)} new channel partner records")

    @api.model
    def default_get(self, fields):
        """Auto-populate attendees based on context"""
        defaults = super().default_get(fields)

        # Check if we have course context from URL or previous action
        if self.env.context.get('default_course_id'):
            course_id = self.env.context.get('default_course_id')
        elif self.env.context.get('active_model') == 'slide.channel' and self.env.context.get('active_id'):
            course_id = self.env.context.get('active_id')
        else:
            # Look for course in current session or user preferences
            course_id = self._get_current_course()

        if course_id:
            defaults['course_id'] = course_id
            channel_partners = self.env['slide.channel.partner'].search([
                ('channel_id', '=', course_id)
            ])
            defaults['attendees_ids'] = [(6, 0, channel_partners.mapped('partner_id').ids)]

        return defaults

    def _get_current_course(self):
        """Get the most recent or relevant course for the user"""
        # Option 1: Get the most recently accessed course by current user
        recent_course = self.env['slide.channel'].search([
            ('channel_partner_ids.partner_id', '=', self.env.user.partner_id.id)
        ], limit=1, order='write_date desc')

        if recent_course:
            return recent_course.id

        # Option 2: Get the most popular/active course
        active_course = self.env['slide.channel'].search([], limit=1, order='total_views desc')
        return active_course.id if active_course else False



