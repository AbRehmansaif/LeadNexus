from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from django.contrib import messages

from .models import Affiliate, AffiliateEarning, PayoutRequest, AffiliateSettings


# ─────────────────────────────────────────────────────────────────────────────
@admin.register(AffiliateSettings)
class AffiliateSettingsAdmin(admin.ModelAdmin):
    list_display = (
        'commission_rate', 'referral_discount_rate',
        'minimum_payout', 'auto_approve_affiliates', 'cookie_duration_days',
    )
    fieldsets = (
        ('Commission', {
            'fields': ('commission_rate', 'referral_discount_rate'),
            'description': 'Commission the affiliate earns and how much their referrals save.',
        }),
        ('Approval & Payouts', {
            'fields': ('auto_approve_affiliates', 'minimum_payout', 'cookie_duration_days'),
        }),
    )

    def has_add_permission(self, request):
        return not AffiliateSettings.objects.exists()


# ─────────────────────────────────────────────────────────────────────────────
@admin.register(Affiliate)
class AffiliateAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'full_name', 'status_badge', 'payout_method_badge',
        'total_signups', 'total_paid_conversions',
        'total_earnings_display', 'available_balance_display',
        'created_at',
    )
    list_filter  = ('status', 'payout_method', 'promotion_method', 'created_at')
    search_fields = (
        'user__username', 'user__email',
        'referral_code', 'full_name', 'phone_number',
    )
    actions = ['action_approve', 'action_reject', 'action_suspend']
    ordering = ['-created_at']

    readonly_fields = (
        'referral_code', 'created_at', 'updated_at',
        'total_earnings', 'paid_out', 'total_signups',
        'total_paid_conversions', 'total_revenue',
        'available_balance_display',
        'payout_details_panel',      # decrypted payout info
    )

    fieldsets = (
        ('👤 Account', {
            'fields': ('user', 'referral_code', 'status', 'rejection_reason'),
        }),
        ('🪪 Identity & Profile', {
            'fields': (
                'full_name', 'phone_number', 'country',
                'promotion_method', 'website_url', 'audience_size', 'bio',
            ),
        }),
        ('💳 Payout Configuration', {
            'fields': ('payout_method', 'payout_details_panel'),
            'description': (
                '⚠ Account details below are decrypted for safe viewing by admins only. '
                'Raw encrypted values are stored in the database.'
            ),
        }),
        ('📊 Financials (read-only)', {
            'fields': (
                'total_earnings', 'paid_out', 'available_balance_display',
                'total_signups', 'total_paid_conversions', 'total_revenue',
            ),
        }),
        ('🗂 Admin Notes', {
            'fields': ('admin_notes', 'reviewed_at', 'reviewed_by'),
        }),
        ('🕓 Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    # ── Display helpers ────────────────────────────────────────────────────
    @admin.display(description='Status')
    def status_badge(self, obj):
        colors = {
            'pending':   ('#f59e0b', '#1c1410', '⏳'),
            'active':    ('#10b981', '#0a1f18', '✓'),
            'suspended': ('#ef4444', '#1f0a0a', '⚠'),
            'rejected':  ('#ef4444', '#1f0a0a', '✗'),
        }
        c, bg, icon = colors.get(obj.status, ('#6b7280', '#111', '?'))
        return format_html(
            '<span style="background:{};color:{};padding:3px 10px;border-radius:100px;'
            'font-size:0.78rem;font-weight:800;">{} {}</span>',
            bg, c, icon, obj.get_status_display()
        )

    @admin.display(description='Payout')
    def payout_method_badge(self, obj):
        icons = {'easypaisa': '📱 EasyPaisa', 'paypal': '💳 PayPal', 'bank': '🏦 Bank'}
        return format_html(
            '<span style="font-size:0.82rem;font-weight:700;">{}</span>',
            icons.get(obj.payout_method, obj.payout_method)
        )

    @admin.display(description='Total Earned')
    def total_earnings_display(self, obj):
        return format_html(
            '<strong style="color:#10b981;">{}</strong>',
            f"{obj.total_earnings:.2f}"
        )

    @admin.display(description='Available Balance')
    def available_balance_display(self, obj):
        bal = obj.available_balance
        color = '#10b981' if bal > 0 else '#6b7280'
        return format_html('<strong style="color:{}">{}</strong>', color, f"{bal:.2f}")

    @admin.display(description='🔓 Decrypted Payout Details')
    def payout_details_panel(self, obj):
        """Shows decrypted payment details for admin to process fund transfers."""
        rows = []
        m = obj.payout_method

        if m == 'easypaisa':
            rows = [
                ('Method',           '📱 EasyPaisa (PKR)'),
                ('Account Holder',   obj.get_easypaisa_name()   or '—'),
                ('Mobile Number',    obj.get_easypaisa_number()  or '—'),
                ('Transfer Via',     'EasyPaisa App → Send Money → Mobile Number'),
            ]
        elif m == 'paypal':
            rows = [
                ('Method',       '💳 PayPal (USD)'),
                ('PayPal Email', obj.get_paypal_email() or '—'),
                ('Transfer Via', 'PayPal Dashboard → Send & Request → Send Money'),
            ]
        elif m == 'bank':
            rows = [
                ('Method',          '🏦 Bank Transfer'),
                ('Account Holder',  obj.get_bank_account_name()   or '—'),
                ('Bank Name',       obj.get_bank_name()            or '—'),
                ('Account / IBAN',  obj.get_bank_account_number()  or '—'),
                ('SWIFT / BIC',     obj.get_bank_swift_code()      or 'N/A'),
            ]

        if not rows:
            return format_html('<span style="color:#6b7280;">No payout account configured.</span>')

        table_rows = ''.join(
            f'<tr><td style="padding:8px 12px;color:#9ca3af;font-weight:600;border-bottom:1px solid #1e2d47;white-space:nowrap;">{k}</td>'
            f'<td style="padding:8px 12px;color:#fff;font-weight:700;border-bottom:1px solid #1e2d47;font-family:monospace;">{v}</td></tr>'
            for k, v in rows
        )
        return format_html(
            '<div style="background:#0f172a;border:1px solid #1e2d47;border-radius:10px;overflow:hidden;max-width:520px;">'
            '<div style="background:#1e2d47;padding:8px 14px;font-size:0.72rem;font-weight:800;color:#60a5fa;text-transform:uppercase;letter-spacing:0.06em;">'
            '🔓 Decrypted — For Admin Use Only</div>'
            '<table style="width:100%;border-collapse:collapse;">{}</table></div>',
            format_html(table_rows)
        )

    # ── Bulk Actions ───────────────────────────────────────────────────────
    @admin.action(description='✅ Approve selected affiliates')
    def action_approve(self, request, queryset):
        updated = queryset.filter(status='pending').update(
            status='active',
            reviewed_at=timezone.now(),
            reviewed_by=request.user,
        )
        self.message_user(request, f'{updated} affiliate(s) approved and activated.', messages.SUCCESS)

    @admin.action(description='✗ Reject selected affiliates')
    def action_reject(self, request, queryset):
        updated = queryset.exclude(status='rejected').update(
            status='rejected',
            reviewed_at=timezone.now(),
            reviewed_by=request.user,
        )
        self.message_user(
            request,
            f'{updated} affiliate(s) rejected. Open each record to add a rejection reason.',
            messages.WARNING
        )

    @admin.action(description='🚫 Suspend selected affiliates')
    def action_suspend(self, request, queryset):
        updated = queryset.filter(status='active').update(status='suspended')
        self.message_user(request, f'{updated} affiliate(s) suspended.', messages.WARNING)

    def save_model(self, request, obj, form, change):
        if change:
            obj.reviewed_by = request.user
            if obj.status in ('active', 'rejected', 'suspended') and not obj.reviewed_at:
                obj.reviewed_at = timezone.now()
        super().save_model(request, obj, form, change)


# ─────────────────────────────────────────────────────────────────────────────
@admin.register(AffiliateEarning)
class AffiliateEarningAdmin(admin.ModelAdmin):
    list_display = (
        'affiliate', 'referred_user', 'plan_name',
        'plan_price', 'commission_rate', 'commission_amount_display',
        'is_paid_out', 'created_at',
    )
    list_filter  = ('is_paid_out', 'plan_name', 'created_at')
    search_fields = ('affiliate__user__username', 'referred_user__username')
    readonly_fields = ('created_at',)
    list_editable = ('is_paid_out',)

    @admin.display(description='Commission')
    def commission_amount_display(self, obj):
        return format_html(
            '<strong style="color:#10b981;">{}</strong>',
            f"{obj.commission_amount:.2f}"
        )


# ─────────────────────────────────────────────────────────────────────────────
@admin.register(PayoutRequest)
class PayoutRequestAdmin(admin.ModelAdmin):
    list_display = (
        'affiliate', 'amount_display', 'payout_method',
        'status_badge', 'requested_at', 'processed_at', 'transfer_info',
    )
    list_filter  = ('status', 'payout_method', 'requested_at')
    search_fields = ('affiliate__user__username', 'affiliate__user__email')
    readonly_fields = ('requested_at', 'processed_at', 'decrypted_snapshot_panel')
    ordering = ['-requested_at']

    fieldsets = (
        ('📋 Request Details', {
            'fields': ('affiliate', 'amount', 'payout_method', 'status', 'admin_notes'),
        }),
        ('🔓 Transfer Details (Decrypted)', {
            'fields': ('decrypted_snapshot_panel',),
            'description': 'Payment account snapshot captured at time of request — safe to use for fund transfer.',
        }),
        ('🕓 Timestamps', {
            'fields': ('requested_at', 'processed_at'),
        }),
    )

    @admin.display(description='Amount')
    def amount_display(self, obj):
        return format_html(
            '<strong style="color:#10b981;font-size:1rem;">{}</strong>',
            f"{obj.amount:.2f}"
        )

    @admin.display(description='Status')
    def status_badge(self, obj):
        colors = {
            'pending':  ('#f59e0b', '#1c1410', '⏳'),
            'approved': ('#818cf8', '#10112a', '✓'),
            'paid':     ('#10b981', '#0a1f18', '💸'),
            'rejected': ('#ef4444', '#1f0a0a', '✗'),
        }
        c, bg, icon = colors.get(obj.status, ('#6b7280', '#111', '?'))
        return format_html(
            '<span style="background:{};color:{};padding:3px 10px;border-radius:100px;'
            'font-size:0.78rem;font-weight:800;">{} {}</span>',
            bg, c, icon, obj.get_status_display()
        )

    @admin.display(description='Transfer To')
    def transfer_info(self, obj):
        """Quick summary of where to send the money."""
        snap = obj.get_snapshot()
        if snap:
            return format_html(
                '<span style="font-size:0.8rem;color:#c4b5fd;font-weight:700;">{} → {}</span>',
                snap.get('method', obj.payout_method),
                snap.get('secondary', '—'),
            )
        # Fallback: read live from affiliate
        aff = obj.affiliate
        summary = aff.get_payout_summary()
        if summary:
            return format_html(
                '<span style="font-size:0.8rem;color:#c4b5fd;font-weight:700;">{} → {}</span>',
                summary.get('method', ''),
                summary.get('secondary', '—'),
            )
        return '—'

    @admin.display(description='🔓 Decrypted Transfer Details')
    def decrypted_snapshot_panel(self, obj):
        """Decrypts and displays the payment snapshot for safe fund processing."""
        snap = obj.get_snapshot()

        if not snap:
            # Fallback: show live affiliate details
            aff = obj.affiliate
            m   = aff.payout_method
            if m == 'easypaisa':
                rows = [
                    ('Source',        'Live affiliate record (no snapshot)'),
                    ('Method',        '📱 EasyPaisa (PKR)'),
                    ('Account Holder', aff.get_easypaisa_name()  or '—'),
                    ('Mobile Number',  aff.get_easypaisa_number() or '—'),
                ]
            elif m == 'paypal':
                rows = [
                    ('Source',       'Live affiliate record (no snapshot)'),
                    ('Method',       '💳 PayPal (USD)'),
                    ('PayPal Email', aff.get_paypal_email() or '—'),
                ]
            elif m == 'bank':
                rows = [
                    ('Source',         'Live affiliate record (no snapshot)'),
                    ('Method',         '🏦 Bank Transfer'),
                    ('Account Holder', aff.get_bank_account_name()  or '—'),
                    ('Bank',           aff.get_bank_name()           or '—'),
                    ('IBAN / Number',  aff.get_bank_account_number() or '—'),
                    ('SWIFT',          aff.get_bank_swift_code()     or 'N/A'),
                ]
            else:
                return format_html('<span style="color:#6b7280;">No details available.</span>')
        else:
            rows = [('Method', snap.get('method', '—')),
                    ('Account', snap.get('primary', '—')),
                    ('Details', snap.get('secondary', '—'))]

        table_rows = ''.join(
            f'<tr><td style="padding:8px 14px;color:#9ca3af;font-weight:600;border-bottom:1px solid #1e2d47;white-space:nowrap;">{k}</td>'
            f'<td style="padding:8px 14px;color:#fff;font-weight:700;border-bottom:1px solid #1e2d47;font-family:monospace;">{v}</td></tr>'
            for k, v in rows
        )
        return format_html(
            '<div style="background:#0f172a;border:2px solid #7c3aed;border-radius:10px;overflow:hidden;max-width:560px;">'
            '<div style="background:#1e0a47;padding:10px 14px;font-size:0.72rem;font-weight:800;color:#c4b5fd;text-transform:uppercase;letter-spacing:0.06em;">'
            '🔓 Verified Transfer Details — Use these to process payment</div>'
            '<table style="width:100%;border-collapse:collapse;">{}</table>'
            '<div style="padding:10px 14px;font-size:0.72rem;color:#475569;border-top:1px solid #1e2d47;">'
            '⚠ Only accept account details from this panel. Never process transfers based on email requests.</div></div>',
            format_html(table_rows)
        )

    def save_model(self, request, obj, form, change):
        if change and obj.status == 'paid' and not obj.processed_at:
            obj.processed_at = timezone.now()
            aff = obj.affiliate
            if not aff.payout_requests.filter(status='paid', id=obj.id).exists():
                aff.paid_out = (aff.paid_out or 0) + obj.amount
                aff.save(update_fields=['paid_out'])
        super().save_model(request, obj, form, change)
