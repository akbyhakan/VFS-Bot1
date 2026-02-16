import { useState } from 'react';
import { useForm, UseFormRegister } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Loading } from '@/components/common/Loading';
import { Calendar, Plus, Trash2, User, MapPin, Globe, Eye, Copy, RotateCcw, List } from 'lucide-react';
import { Modal } from '@/components/ui/Modal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { useConfirmDialog } from '@/hooks/useConfirmDialog';
import { toast } from 'sonner';
import {
  useCountries,
  useCentres,
  useCreateAppointmentRequest,
  useAppointmentRequests,
  useDeleteAppointmentRequest,
} from '@/hooks/useAppointmentRequest';
import type { AppointmentRequest, AppointmentPerson, AppointmentRequestResponse } from '@/types/appointment';
import {
  validateBirthDate,
  validatePassportIssueDate,
  validatePassportExpiryDate,
  validateEmail,
  validateTurkishPhone,
} from '@/utils/validators/appointment';
import { AppointmentCalendar } from '@/components/appointments/AppointmentCalendar';

// Alias for consistency with existing code
const validatePhoneNumber = validateTurkishPhone;

export default function AppointmentRequest() {
  const { t } = useTranslation();
  const [personCount, setPersonCount] = useState<number>(1);
  const [selectedCountry, setSelectedCountry] = useState<string>('');
  const [selectedCentres, setSelectedCentres] = useState<string[]>([]);
  const [selectedDates, setSelectedDates] = useState<string[]>([]);
  const [dateInput, setDateInput] = useState<string>('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [viewingRequest, setViewingRequest] = useState<AppointmentRequestResponse | null>(null);
  const [viewMode, setViewMode] = useState<'list' | 'calendar'>('list');
  const { isOpen: isConfirmOpen, options: confirmOptions, confirm, handleConfirm, handleCancel: handleConfirmCancel } = useConfirmDialog();

  const { data: countries, isLoading: loadingCountries } = useCountries();
  const { data: centres, isLoading: loadingCentres } = useCentres(selectedCountry);
  const { data: requests, isLoading: loadingRequests } = useAppointmentRequests();
  const createRequest = useCreateAppointmentRequest();
  const deleteRequest = useDeleteAppointmentRequest();

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
  } = useForm<AppointmentRequest>({
    defaultValues: {
      country_code: '',
      centres: [],
      preferred_dates: [],
      person_count: 1,
      persons: [getEmptyPerson()],
    },
  });

  function getEmptyPerson(): AppointmentPerson {
    return {
      first_name: '',
      last_name: '',
      gender: 'male',
      nationality: 'Turkey',
      birth_date: '',
      passport_number: '',
      passport_issue_date: '',
      passport_expiry_date: '',
      phone_code: '90',
      phone_number: '',
      email: '',
      is_child_with_parent: false,
    };
  }

  const handlePersonCountChange = (count: number) => {
    setPersonCount(count);
    const currentPersons = watch('persons') || [];
    const newPersons = Array.from({ length: count }, (_, i) =>
      currentPersons[i] || getEmptyPerson()
    );
    setValue('persons', newPersons);
  };

  const handleCentreToggle = (centre: string) => {
    setSelectedCentres((prev) =>
      prev.includes(centre) ? prev.filter((c) => c !== centre) : [...prev, centre]
    );
  };

  const handleAddDate = () => {
    if (!dateInput) return;
    if (!selectedDates.includes(dateInput)) {
      setSelectedDates([...selectedDates, dateInput]);
    }
    setDateInput('');
  };

  const handleRemoveDate = (date: string) => {
    setSelectedDates(selectedDates.filter((d) => d !== date));
  };

  const validateForm = (data: AppointmentRequest): boolean => {
    const newErrors: Record<string, string> = {};

    if (!selectedCountry) {
      newErrors.country = t('appointmentRequest.selectCountryError');
    }

    if (selectedCentres.length === 0) {
      newErrors.centres = t('appointmentRequest.selectCentreError');
    }

    if (selectedDates.length === 0) {
      newErrors.dates = t('appointmentRequest.selectDateError');
    }

    data.persons.forEach((person, index) => {
      if (!person.first_name) {
        newErrors[`person_${index}_first_name`] = t('appointmentRequest.firstNameRequired');
      }
      if (!person.last_name) {
        newErrors[`person_${index}_last_name`] = t('appointmentRequest.lastNameRequired');
      }
      if (!person.birth_date) {
        newErrors[`person_${index}_birth_date`] = t('appointmentRequest.birthDateRequired');
      } else if (!validateBirthDate(person.birth_date)) {
        newErrors[`person_${index}_birth_date`] = t('appointmentRequest.birthDateInvalid');
      }
      if (!person.passport_number) {
        newErrors[`person_${index}_passport_number`] = t('appointmentRequest.passportNumberRequired');
      }
      if (!person.passport_issue_date) {
        newErrors[`person_${index}_passport_issue_date`] = t('appointmentRequest.passportIssueRequired');
      } else if (!validatePassportIssueDate(person.passport_issue_date)) {
        newErrors[`person_${index}_passport_issue_date`] =
          t('appointmentRequest.passportIssueInvalid');
      }
      if (!person.passport_expiry_date) {
        newErrors[`person_${index}_passport_expiry_date`] = t('appointmentRequest.passportExpiryRequired');
      } else if (!validatePassportExpiryDate(person.passport_expiry_date)) {
        newErrors[`person_${index}_passport_expiry_date`] =
          t('appointmentRequest.passportExpiryInvalid');
      }
      if (!person.phone_number) {
        newErrors[`person_${index}_phone_number`] = t('appointmentRequest.phoneRequired');
      } else if (!validatePhoneNumber(person.phone_number)) {
        newErrors[`person_${index}_phone_number`] =
          t('appointmentRequest.phoneInvalid');
      }
      if (!person.email) {
        newErrors[`person_${index}_email`] = t('appointmentRequest.emailRequired');
      } else if (!validateEmail(person.email)) {
        newErrors[`person_${index}_email`] = t('appointmentRequest.emailInvalid');
      }
    });

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const onSubmit = async (data: AppointmentRequest) => {
    data.country_code = selectedCountry;
    data.centres = selectedCentres;
    data.preferred_dates = selectedDates;
    data.person_count = personCount;

    if (!validateForm(data)) {
      toast.error(t('appointmentRequest.fillAllFields'));
      return;
    }

    try {
      await createRequest.mutateAsync(data);
      toast.success(t('appointmentRequest.requestCreated'));
      reset();
      setPersonCount(1);
      setSelectedCountry('');
      setSelectedCentres([]);
      setSelectedDates([]);
      setErrors({});
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('appointmentRequest.deleteFailed'));
    }
  };

  const handleDelete = async (id: number) => {
    const confirmed = await confirm({
      title: t('appointmentRequest.deleteRequestTitle'),
      message: t('appointmentRequest.deleteRequestMessage'),
      confirmText: t('appointmentRequest.deleteConfirm'),
      cancelText: t('appointmentRequest.deleteCancel'),
      variant: 'danger',
    });

    if (!confirmed) return;

    try {
      await deleteRequest.mutateAsync(id);
      toast.success(t('appointmentRequest.requestDeleted'));
    } catch (error) {
      toast.error(t('appointmentRequest.deleteFailed'));
    }
  };

  const handleView = (request: AppointmentRequestResponse) => {
    setViewingRequest(request);
  };

  const handleCopyRequest = (request: AppointmentRequestResponse) => {
    setSelectedCountry(request.country_code);
    setSelectedCentres([...request.centres]);
    setSelectedDates([...request.preferred_dates]);
    setPersonCount(request.person_count);
    setValue('persons', request.persons.map(p => ({ ...p })));
    toast.success(t('appointmentRequest.copiedToForm'));
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleClearForm = () => {
    reset();
    setPersonCount(1);
    setSelectedCountry('');
    setSelectedCentres([]);
    setSelectedDates([]);
    setErrors({});
    toast.info(t('appointmentRequest.formCleared'));
  };

  if (loadingCountries) return <Loading />;

  return (
    <div className="space-y-6">
      {/* Form Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Plus className="h-5 w-5" />
            {t('appointmentRequest.title')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
            {/* Ana Bilgiler */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">{t('appointmentRequest.mainInfo')}</h3>

              {/* Kişi Sayısı */}
              <div>
                <label htmlFor="person-count" className="block text-sm font-medium mb-2">
                  {t('appointmentRequest.personCount')}
                </label>
                <select
                  id="person-count"
                  value={personCount}
                  onChange={(e) => handlePersonCountChange(Number(e.target.value))}
                  className="w-full px-3 py-2 border border-dark-600 rounded-lg bg-dark-800 text-dark-100 focus:outline-none focus:ring-2 focus:ring-primary-500"
                  aria-describedby="person-count-hint"
                >
                  {[1, 2, 3, 4, 5, 6].map((num) => (
                    <option key={num} value={num}>
                      {t('appointmentRequest.persons', { count: num })}
                    </option>
                  ))}
                </select>
                <span id="person-count-hint" className="sr-only">
                  {t('appointmentRequest.personCountHint')}
                </span>
              </div>

              {/* Hedef Ülke */}
              <div>
                <label htmlFor="target-country" className="block text-sm font-medium mb-2">
                  <Globe className="inline h-4 w-4 mr-1" aria-hidden="true" />
                  {t('appointmentRequest.targetCountry')}
                </label>
                <select
                  id="target-country"
                  value={selectedCountry}
                  onChange={(e) => {
                    setSelectedCountry(e.target.value);
                    setSelectedCentres([]);
                  }}
                  className="w-full px-3 py-2 border border-dark-600 rounded-lg bg-dark-800 text-dark-100 focus:outline-none focus:ring-2 focus:ring-primary-500"
                  aria-required="true"
                  aria-invalid={!!errors.country}
                  aria-describedby={errors.country ? 'country-error' : undefined}
                >
                  <option value="">{t('appointmentRequest.selectCountry')}</option>
                  {countries?.map((country) => (
                    <option key={country.code} value={country.code}>
                      {country.name_tr} ({country.name_en})
                    </option>
                  ))}
                </select>
                {errors.country && (
                  <p id="country-error" className="text-red-500 text-sm mt-1" role="alert">
                    {errors.country}
                  </p>
                )}
              </div>

              {/* Merkezler */}
              {selectedCountry && (
                <div>
                  <label className="block text-sm font-medium mb-2">
                    <MapPin className="inline h-4 w-4 mr-1" />
                    {t('appointmentRequest.centres')}
                  </label>
                  {loadingCentres ? (
                    <Loading />
                  ) : (
                    <div className="space-y-2">
                      {centres?.map((centre) => (
                        <label key={centre} className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={selectedCentres.includes(centre)}
                            onChange={() => handleCentreToggle(centre)}
                            className="h-4 w-4"
                          />
                          <span>{centre}</span>
                        </label>
                      ))}
                    </div>
                  )}
                  {errors.centres && <p className="text-red-500 text-sm mt-1">{errors.centres}</p>}
                </div>
              )}

              {/* Tarihler */}
              <div>
                <label className="block text-sm font-medium mb-2">
                  <Calendar className="inline h-4 w-4 mr-1" />
                  {t('appointmentRequest.preferredDates')}
                </label>
                <div className="flex gap-2 mb-2">
                  <Input
                    type="text"
                    placeholder={t('appointmentRequest.datePlaceholder')}
                    value={dateInput}
                    onChange={(e) => setDateInput(e.target.value)}
                    className="flex-1"
                  />
                  <Button type="button" onClick={handleAddDate}>
                    {t('appointmentRequest.add')}
                  </Button>
                </div>
                <div className="flex flex-wrap gap-2">
                  {selectedDates.map((date) => (
                    <span
                      key={date}
                      className="inline-flex items-center gap-1 px-3 py-1 bg-green-600 rounded-md text-sm"
                    >
                      {date}
                      <button
                        type="button"
                        onClick={() => handleRemoveDate(date)}
                        className="ml-1 hover:text-red-300"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
                {errors.dates && <p className="text-red-500 text-sm mt-1">{errors.dates}</p>}
              </div>
            </div>

            {/* Kişi Bilgileri */}
            {Array.from({ length: personCount }).map((_, index) => (
              <PersonForm
                key={index}
                index={index}
                register={register}
                errors={errors}
              />
            ))}

            <div className="flex justify-end gap-3">
              <Button 
                type="button" 
                variant="secondary"
                onClick={handleClearForm}
                leftIcon={<RotateCcw className="w-4 h-4" />}
              >
                {t('appointmentRequest.clearForm')}
              </Button>
              <Button type="submit" disabled={createRequest.isPending}>
                {createRequest.isPending ? t('appointmentRequest.saving') : `💾 ${t('appointmentRequest.saveRequest')}`}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Mevcut Talepler */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>{t('appointmentRequest.existingRequests')}</CardTitle>
            <div className="flex gap-2">
              <Button
                variant={viewMode === 'list' ? 'primary' : 'outline'}
                size="sm"
                onClick={() => setViewMode('list')}
              >
                <List className="h-4 w-4 mr-2" />
                {t('appointmentRequest.listView')}
              </Button>
              <Button
                variant={viewMode === 'calendar' ? 'primary' : 'outline'}
                size="sm"
                onClick={() => setViewMode('calendar')}
              >
                <Calendar className="h-4 w-4 mr-2" />
                {t('appointmentRequest.calendarView')}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {loadingRequests ? (
            <Loading />
          ) : requests && requests.length > 0 ? (
            viewMode === 'calendar' ? (
              <AppointmentCalendar appointments={requests} />
            ) : (
              <div className="space-y-4">
                {requests.map((request) => (
                  <div
                    key={request.id}
                    className="p-4 border border-dark-600 rounded-md bg-dark-800"
                  >
                    <div className="flex justify-between items-start">
                      <div>
                        <p className="font-semibold">
                          {t('appointmentRequest.requestId', { id: request.id, status: request.status })}
                        </p>
                        <p className="text-sm text-dark-400">
                          {t('appointmentRequest.country')}: {request.country_code} | {t('appointmentRequest.personCountValue', { count: request.person_count })}
                        </p>
                        <p className="text-sm text-dark-400">
                          {t('appointmentRequest.date')}: {new Date(request.created_at).toLocaleDateString('tr-TR')}
                        </p>
                      </div>
                      <div className="flex gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleView(request)}
                          title={t('appointmentRequest.viewDetails')}
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleCopyRequest(request)}
                          title={t('appointmentRequest.copyToForm')}
                        >
                          <Copy className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="danger"
                          size="sm"
                          onClick={() => handleDelete(request.id)}
                          title={t('appointmentRequest.deleteRequest')}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )
          ) : (
            <p className="text-dark-400 text-center">{t('appointmentRequest.noRequests')}</p>
          )}
        </CardContent>
      </Card>

      {/* Detay Modal */}
      {viewingRequest && (
        <Modal
          isOpen={!!viewingRequest}
          onClose={() => setViewingRequest(null)}
          title={t('appointmentRequest.requestDetails', { id: viewingRequest.id })}
          size="lg"
        >
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm text-dark-400">{t('appointmentRequest.statusLabel')}</label>
                <p className="font-medium">{viewingRequest.status}</p>
              </div>
              <div>
                <label className="text-sm text-dark-400">{t('appointmentRequest.countryLabel')}</label>
                <p className="font-medium">{viewingRequest.country_code}</p>
              </div>
              <div>
                <label className="text-sm text-dark-400">{t('appointmentRequest.personCountLabel')}</label>
                <p className="font-medium">{viewingRequest.person_count}</p>
              </div>
              <div>
                <label className="text-sm text-dark-400">{t('appointmentRequest.created')}</label>
                <p className="font-medium">{new Date(viewingRequest.created_at).toLocaleString('tr-TR')}</p>
              </div>
            </div>
            
            <div>
              <label className="text-sm text-dark-400">{t('appointmentRequest.centresLabel')}</label>
              <div className="flex flex-wrap gap-2 mt-1">
                {viewingRequest.centres.map((centre) => (
                  <span key={centre} className="px-2 py-1 bg-dark-700 rounded text-sm">
                    {centre}
                  </span>
                ))}
              </div>
            </div>
            
            <div>
              <label className="text-sm text-dark-400">{t('appointmentRequest.preferredDatesLabel')}</label>
              <div className="flex flex-wrap gap-2 mt-1">
                {viewingRequest.preferred_dates.map((date) => (
                  <span key={date} className="px-2 py-1 bg-primary-600/20 text-primary-400 rounded text-sm">
                    {date}
                  </span>
                ))}
              </div>
            </div>
            
            <div>
              <label className="text-sm text-dark-400 mb-2 block">{t('appointmentRequest.personsLabel')}</label>
              {viewingRequest.persons.map((person, index) => (
                <div key={index} className="p-3 bg-dark-800 rounded mb-2">
                  <p className="font-medium">{person.first_name} {person.last_name}</p>
                  <p className="text-sm text-dark-400">{person.email} | +{person.phone_code} {person.phone_number}</p>
                  <p className="text-sm text-dark-400">{t('appointmentRequest.passportNumber')}: {person.passport_number}</p>
                </div>
              ))}
            </div>
            
            <div className="flex justify-end gap-2 pt-4">
              <Button variant="secondary" onClick={() => setViewingRequest(null)}>
                {t('appointmentRequest.close')}
              </Button>
              <Button variant="primary" onClick={() => {
                handleCopyRequest(viewingRequest);
                setViewingRequest(null);
              }}>
                <Copy className="w-4 h-4 mr-2" />
                {t('appointmentRequest.copyToFormBtn')}
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Confirm Dialog */}
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
          isLoading={deleteRequest.isPending}
        />
      )}
    </div>
  );
}

// Person Form Component
function PersonForm({
  index,
  register,
  errors,
}: {
  index: number;
  register: UseFormRegister<AppointmentRequest>;
  errors: Record<string, string>;
}) {
  const { t } = useTranslation();
  return (
    <div className="space-y-4 p-4 border border-dark-600 rounded-md bg-dark-800">
      <h3 className="text-lg font-semibold flex items-center gap-2">
        <User className="h-5 w-5" />
        {t('appointmentRequest.personInfo', { number: index + 1 })}
      </h3>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium mb-2">{t('appointmentRequest.firstName')}</label>
          <Input {...register(`persons.${index}.first_name`)} />
          {errors[`person_${index}_first_name`] && (
            <p className="text-red-500 text-sm mt-1">{errors[`person_${index}_first_name`]}</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium mb-2">{t('appointmentRequest.lastName')}</label>
          <Input {...register(`persons.${index}.last_name`)} />
          {errors[`person_${index}_last_name`] && (
            <p className="text-red-500 text-sm mt-1">{errors[`person_${index}_last_name`]}</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium mb-2">{t('appointmentRequest.nationality')}</label>
          <Input {...register(`persons.${index}.nationality`)} defaultValue="Turkey" readOnly />
        </div>

        <div>
          <label className="block text-sm font-medium mb-2">{t('appointmentRequest.birthDate')}</label>
          <Input {...register(`persons.${index}.birth_date`)} placeholder={t('appointmentRequest.birthDatePlaceholder')} />
          {errors[`person_${index}_birth_date`] && (
            <p className="text-red-500 text-sm mt-1">{errors[`person_${index}_birth_date`]}</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium mb-2">{t('appointmentRequest.passportNumber')}</label>
          <Input {...register(`persons.${index}.passport_number`)} placeholder={t('appointmentRequest.passportPlaceholder')} />
          {errors[`person_${index}_passport_number`] && (
            <p className="text-red-500 text-sm mt-1">{errors[`person_${index}_passport_number`]}</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium mb-2">
            {t('appointmentRequest.passportIssue')}
          </label>
          <Input {...register(`persons.${index}.passport_issue_date`)} placeholder={t('appointmentRequest.passportIssuePlaceholder')} />
          {errors[`person_${index}_passport_issue_date`] && (
            <p className="text-red-500 text-sm mt-1">
              {errors[`person_${index}_passport_issue_date`]}
            </p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium mb-2">
            {t('appointmentRequest.passportExpiry')}
          </label>
          <Input {...register(`persons.${index}.passport_expiry_date`)} placeholder={t('appointmentRequest.passportExpiryPlaceholder')} />
          {errors[`person_${index}_passport_expiry_date`] && (
            <p className="text-red-500 text-sm mt-1">
              {errors[`person_${index}_passport_expiry_date`]}
            </p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium mb-2">{t('appointmentRequest.phone')}</label>
          <div className="flex gap-2">
            <Input
              {...register(`persons.${index}.phone_code`)}
              defaultValue="90"
              readOnly
              className="w-20"
            />
            <Input
              {...register(`persons.${index}.phone_number`)}
              placeholder={t('appointmentRequest.phonePlaceholder')}
              className="flex-1"
            />
          </div>
          {errors[`person_${index}_phone_number`] && (
            <p className="text-red-500 text-sm mt-1">{errors[`person_${index}_phone_number`]}</p>
          )}
        </div>

        <div className="md:col-span-2">
          <label className="block text-sm font-medium mb-2">{t('appointmentRequest.email')}</label>
          <Input {...register(`persons.${index}.email`)} type="email" placeholder={t('appointmentRequest.emailPlaceholder')} />
          {errors[`person_${index}_email`] && (
            <p className="text-red-500 text-sm mt-1">{errors[`person_${index}_email`]}</p>
          )}
        </div>
      </div>
    </div>
  );
}

