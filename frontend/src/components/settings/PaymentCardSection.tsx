import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { CreditCard, Trash2, Edit, Save, X, Plus } from 'lucide-react';
import { usePaymentCard } from '@/hooks/usePaymentCard';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { useConfirmDialog } from '@/hooks/useConfirmDialog';
import { validateCardForm, formatCardNumber } from '@/utils/validators/creditCard';
import { createFieldChangeHandler } from '@/utils/formHelpers';
import { EMPTY_CARD_FORM, type CardFormData } from '@/constants/forms';
import { toast } from 'sonner';

export function PaymentCardSection() {
  const { t } = useTranslation();
  const { card, loading, error, saving, deleting, saveCard, deleteCard } = usePaymentCard();
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState<CardFormData>({ ...EMPTY_CARD_FORM });
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const { isOpen: isConfirmOpen, options: confirmOptions, confirm, handleConfirm, handleCancel: handleConfirmCancel } = useConfirmDialog();

  const handleHolderChange = createFieldChangeHandler(
    setFormData, setFormErrors, 'card_holder_name', 'cardholderName',
  );

  const handleNumberChange = createFieldChangeHandler(
    setFormData, setFormErrors, 'card_number', 'cardNumber',
    (value) => {
      const raw = value.replace(/\s/g, '');
      if (/^\d*$/.test(raw) && raw.length <= 19) return raw;
      return null;
    },
  );

  const handleMonthChange = createFieldChangeHandler(
    setFormData, setFormErrors, 'expiry_month', 'expiryMonth',
    (value) => (/^\d{0,2}$/.test(value) ? value : null),
  );

  const handleYearChange = createFieldChangeHandler(
    setFormData, setFormErrors, 'expiry_year', 'expiryYear',
    (value) => (/^\d{0,4}$/.test(value) ? value : null),
  );

  const handleCvvChange = createFieldChangeHandler(
    setFormData, setFormErrors, 'cvv', 'cvv',
    (value) => (/^\d{0,4}$/.test(value) ? value : null),
  );

  const handleEdit = () => {
    setFormData(
      card
        ? { card_holder_name: card.card_holder_name, card_number: '', expiry_month: card.expiry_month, expiry_year: card.expiry_year }
        : { ...EMPTY_CARD_FORM },
    );
    setIsEditing(true);
  };

  const handleCancel = () => {
    setIsEditing(false);
    setFormData({ ...EMPTY_CARD_FORM });
  };

  const handleSave = async () => {
    const validation = validateCardForm(formData);
    if (!validation.isValid) {
      setFormErrors(validation.errors);
      toast.error(t('settings.fixFormErrors'));
      return;
    }
    setFormErrors({});
    const success = await saveCard({ ...formData, card_number: formData.card_number.replace(/\s/g, ''), cvv: formData.cvv || undefined });
    if (success) {
      setIsEditing(false);
      setFormData({ ...EMPTY_CARD_FORM });
      toast.success(t('settings.cardSaved'));
    }
  };

  const handleDelete = async () => {
    const confirmed = await confirm({
      title: t('settings.deleteCardTitle'),
      message: t('settings.deleteCardMessage'),
      confirmText: t('settings.deleteCardConfirm'),
      cancelText: t('settings.deleteCardCancel'),
      variant: 'danger',
    });
    if (!confirmed) return;
    await deleteCard();
  };

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <CreditCard className="w-5 h-5" />
            {t('settings.creditCard')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-dark-400 text-sm">{t('settings.loading')}</p>
          ) : error ? (
            <p className="text-red-500 text-sm">{error}</p>
          ) : !isEditing && !card ? (
            <div className="text-center py-8">
              <CreditCard className="w-12 h-12 text-dark-500 mx-auto mb-4" />
              <p className="text-dark-400 mb-4">{t('settings.noCard')}</p>
              <Button variant="primary" leftIcon={<Plus className="w-5 h-5" />} onClick={handleEdit}>
                {t('settings.addCard')}
              </Button>
            </div>
          ) : !isEditing && card ? (
            <div className="space-y-4">
              <div>
                <label className="text-sm text-dark-400">{t('settings.cardHolder')}</label>
                <p className="font-medium">{card.card_holder_name}</p>
              </div>
              <div>
                <label className="text-sm text-dark-400">{t('settings.cardNumber')}</label>
                <p className="font-medium font-mono">{card.card_number_masked}</p>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm text-dark-400">{t('settings.expiryDate')}</label>
                  <p className="font-medium">{card.expiry_month}/{card.expiry_year}</p>
                </div>
              </div>
              <div className="flex gap-2 mt-4">
                <Button variant="primary" leftIcon={<Edit className="w-4 h-4" />} onClick={handleEdit}>
                  {t('settings.edit')}
                </Button>
                <Button variant="danger" leftIcon={<Trash2 className="w-4 h-4" />} onClick={handleDelete} isLoading={deleting}>
                  {deleting ? t('settings.deleting') : t('settings.delete')}
                </Button>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-dark-400 mb-1">{t('settings.cardHolderName')}</label>
                <input
                  type="text"
                  value={formData.card_holder_name}
                  onChange={(e) => handleHolderChange(e.target.value)}
                  placeholder="JOHN DOE"
                  className={`w-full px-3 py-2 border rounded bg-dark-800 text-white ${formErrors.cardholderName ? 'border-red-500' : 'border-dark-600'}`}
                />
                {formErrors.cardholderName && <p className="text-red-500 text-xs mt-1">{formErrors.cardholderName}</p>}
              </div>
              <div>
                <label className="block text-sm text-dark-400 mb-1">{t('settings.cardNumber')}</label>
                <input
                  type="text"
                  value={formatCardNumber(formData.card_number)}
                  onChange={(e) => handleNumberChange(e.target.value)}
                  placeholder="4111 1111 1111 1234"
                  maxLength={23}
                  autoComplete="cc-number"
                  inputMode="numeric"
                  className={`w-full px-3 py-2 border rounded bg-dark-800 text-white font-mono ${formErrors.cardNumber ? 'border-red-500' : 'border-dark-600'}`}
                />
                {formErrors.cardNumber && <p className="text-red-500 text-xs mt-1">{formErrors.cardNumber}</p>}
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm text-dark-400 mb-1">{t('settings.month')}</label>
                  <input
                    type="text"
                    value={formData.expiry_month}
                    onChange={(e) => handleMonthChange(e.target.value)}
                    placeholder="12"
                    maxLength={2}
                    inputMode="numeric"
                    className={`w-full px-3 py-2 border rounded bg-dark-800 text-white ${formErrors.expiryMonth ? 'border-red-500' : 'border-dark-600'}`}
                  />
                </div>
                <div>
                  <label className="block text-sm text-dark-400 mb-1">{t('settings.year')}</label>
                  <input
                    type="text"
                    value={formData.expiry_year}
                    onChange={(e) => handleYearChange(e.target.value)}
                    placeholder="2025"
                    maxLength={4}
                    inputMode="numeric"
                    className={`w-full px-3 py-2 border rounded bg-dark-800 text-white ${formErrors.expiryYear ? 'border-red-500' : 'border-dark-600'}`}
                  />
                </div>
                {formErrors.expiryMonth && (
                  <div className="col-span-2">
                    <p className="text-red-500 text-xs mt-1">{formErrors.expiryMonth}</p>
                  </div>
                )}
              </div>
              <div>
                <label className="block text-sm text-dark-400 mb-1">{t('settings.cvv')}</label>
                <input
                  type="password"
                  value={formData.cvv}
                  onChange={(e) => handleCvvChange(e.target.value)}
                  placeholder="123"
                  maxLength={4}
                  inputMode="numeric"
                  autoComplete="cc-csc"
                  className={`w-full px-3 py-2 border rounded bg-dark-800 text-white ${formErrors.cvv ? 'border-red-500' : 'border-dark-600'}`}
                />
                {formErrors.cvv && <p className="text-red-500 text-xs mt-1">{formErrors.cvv}</p>}
              </div>
              <div className="flex gap-2 mt-4">
                <Button variant="primary" leftIcon={<Save className="w-4 h-4" />} onClick={handleSave} isLoading={saving}>
                  {saving ? t('settings.saving') : t('settings.save')}
                </Button>
                {card && (
                  <Button variant="secondary" leftIcon={<X className="w-4 h-4" />} onClick={handleCancel}>
                    {t('settings.cancel')}
                  </Button>
                )}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {confirmOptions && (
        <ConfirmDialog
          isOpen={isConfirmOpen}
          onConfirm={handleConfirm}
          onCancel={handleConfirmCancel}
          title={confirmOptions.title}
          message={confirmOptions.message}
          confirmText={confirmOptions.confirmText}
          cancelText={confirmOptions.cancelText}
          variant={confirmOptions.variant}
          isLoading={deleting}
        />
      )}
    </>
  );
}
