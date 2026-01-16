import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Loading } from '@/components/common/Loading';
import { Calendar, Plus, Trash2, User, MapPin, Globe } from 'lucide-react';
import { toast } from 'sonner';
import {
  useCountries,
  useCentres,
  useCreateAppointmentRequest,
  useAppointmentRequests,
  useDeleteAppointmentRequest,
} from '@/hooks/useAppointmentRequest';
import type { AppointmentRequest, AppointmentPerson } from '@/types/appointment';
import {
  validateBirthDate,
  validatePassportIssueDate,
  validatePassportExpiryDate,
  validateEmail,
  validateTurkishPhone,
} from '@/utils/validators/appointment';

// Alias for consistency with existing code
const validatePhoneNumber = validateTurkishPhone;

export default function AppointmentRequest() {
  const [personCount, setPersonCount] = useState<number>(1);
  const [selectedCountry, setSelectedCountry] = useState<string>('');
  const [selectedCentres, setSelectedCentres] = useState<string[]>([]);
  const [selectedDates, setSelectedDates] = useState<string[]>([]);
  const [dateInput, setDateInput] = useState<string>('');
  const [errors, setErrors] = useState<Record<string, string>>({});

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
      newErrors.country = 'Lütfen bir ülke seçin';
    }

    if (selectedCentres.length === 0) {
      newErrors.centres = 'En az bir merkez seçmelisiniz';
    }

    if (selectedDates.length === 0) {
      newErrors.dates = 'En az bir tarih seçmelisiniz';
    }

    data.persons.forEach((person, index) => {
      if (!person.first_name) {
        newErrors[`person_${index}_first_name`] = 'İsim gerekli';
      }
      if (!person.last_name) {
        newErrors[`person_${index}_last_name`] = 'Soyisim gerekli';
      }
      if (!person.birth_date) {
        newErrors[`person_${index}_birth_date`] = 'Doğum tarihi gerekli';
      } else if (!validateBirthDate(person.birth_date)) {
        newErrors[`person_${index}_birth_date`] = 'Doğum tarihi bugünden ileri olamaz';
      }
      if (!person.passport_number) {
        newErrors[`person_${index}_passport_number`] = 'Pasaport numarası gerekli';
      }
      if (!person.passport_issue_date) {
        newErrors[`person_${index}_passport_issue_date`] = 'Geçerlilik başlangıç gerekli';
      } else if (!validatePassportIssueDate(person.passport_issue_date)) {
        newErrors[`person_${index}_passport_issue_date`] =
          'Geçerlilik başlangıç tarihi bugünden ileri olamaz';
      }
      if (!person.passport_expiry_date) {
        newErrors[`person_${index}_passport_expiry_date`] = 'Geçerlilik bitiş gerekli';
      } else if (!validatePassportExpiryDate(person.passport_expiry_date)) {
        newErrors[`person_${index}_passport_expiry_date`] =
          'Pasaport en az 3 ay daha geçerli olmalıdır';
      }
      if (!person.phone_number) {
        newErrors[`person_${index}_phone_number`] = 'Telefon numarası gerekli';
      } else if (!validatePhoneNumber(person.phone_number)) {
        newErrors[`person_${index}_phone_number`] =
          'Geçerli bir telefon numarası girin (10 hane, 0 ile başlamaz)';
      }
      if (!person.email) {
        newErrors[`person_${index}_email`] = 'E-posta gerekli';
      } else if (!validateEmail(person.email)) {
        newErrors[`person_${index}_email`] = 'Geçerli bir e-posta adresi girin';
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
      toast.error('Lütfen tüm alanları doğru şekilde doldurun');
      return;
    }

    try {
      await createRequest.mutateAsync(data);
      toast.success('Randevu talebi oluşturuldu');
      reset();
      setPersonCount(1);
      setSelectedCountry('');
      setSelectedCentres([]);
      setSelectedDates([]);
      setErrors({});
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'İşlem başarısız');
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Bu talebi silmek istediğinizden emin misiniz?')) return;

    try {
      await deleteRequest.mutateAsync(id);
      toast.success('Talep silindi');
    } catch (error) {
      toast.error('Silme işlemi başarısız');
    }
  };

  if (loadingCountries) return <Loading />;

  return (
    <div className="space-y-6">
      {/* Form Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Plus className="h-5 w-5" />
            Yeni Randevu Talebi Oluştur
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
            {/* Ana Bilgiler */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">Ana Bilgiler</h3>

              {/* Kişi Sayısı */}
              <div>
                <label className="block text-sm font-medium mb-2">Kişi Sayısı</label>
                <select
                  value={personCount}
                  onChange={(e) => handlePersonCountChange(Number(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-600 rounded-md bg-gray-700 text-white"
                >
                  {[1, 2, 3, 4, 5, 6].map((num) => (
                    <option key={num} value={num}>
                      {num} Kişi
                    </option>
                  ))}
                </select>
              </div>

              {/* Hedef Ülke */}
              <div>
                <label className="block text-sm font-medium mb-2">
                  <Globe className="inline h-4 w-4 mr-1" />
                  Hedef Ülke
                </label>
                <select
                  value={selectedCountry}
                  onChange={(e) => {
                    setSelectedCountry(e.target.value);
                    setSelectedCentres([]);
                  }}
                  className="w-full px-3 py-2 border border-gray-600 rounded-md bg-gray-700 text-white"
                >
                  <option value="">Ülke Seçin</option>
                  {countries?.map((country) => (
                    <option key={country.code} value={country.code}>
                      {country.name_tr} ({country.name_en})
                    </option>
                  ))}
                </select>
                {errors.country && <p className="text-red-500 text-sm mt-1">{errors.country}</p>}
              </div>

              {/* Merkezler */}
              {selectedCountry && (
                <div>
                  <label className="block text-sm font-medium mb-2">
                    <MapPin className="inline h-4 w-4 mr-1" />
                    Merkez(ler)
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
                  Tercih Edilen Tarihler (GG/AA/YYYY)
                </label>
                <div className="flex gap-2 mb-2">
                  <Input
                    type="text"
                    placeholder="15/02/2026"
                    value={dateInput}
                    onChange={(e) => setDateInput(e.target.value)}
                    className="flex-1"
                  />
                  <Button type="button" onClick={handleAddDate}>
                    Ekle
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

            <div className="flex justify-end">
              <Button type="submit" disabled={createRequest.isPending}>
                {createRequest.isPending ? 'Kaydediliyor...' : '💾 Talebi Kaydet'}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Mevcut Talepler */}
      <Card>
        <CardHeader>
          <CardTitle>Mevcut Talepler</CardTitle>
        </CardHeader>
        <CardContent>
          {loadingRequests ? (
            <Loading />
          ) : requests && requests.length > 0 ? (
            <div className="space-y-4">
              {requests.map((request) => (
                <div
                  key={request.id}
                  className="p-4 border border-gray-600 rounded-md bg-gray-800"
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="font-semibold">
                        Talep #{request.id} - {request.status}
                      </p>
                      <p className="text-sm text-gray-400">
                        Ülke: {request.country_code} | {request.person_count} Kişi
                      </p>
                      <p className="text-sm text-gray-400">
                        Tarih: {new Date(request.created_at).toLocaleDateString('tr-TR')}
                      </p>
                    </div>
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() => handleDelete(request.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-400 text-center">Henüz talep yok</p>
          )}
        </CardContent>
      </Card>
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
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  register: any;
  errors: Record<string, string>;
}) {
  return (
    <div className="space-y-4 p-4 border border-gray-600 rounded-md bg-gray-800">
      <h3 className="text-lg font-semibold flex items-center gap-2">
        <User className="h-5 w-5" />
        Kişi {index + 1} Bilgileri
      </h3>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium mb-2">İsim</label>
          <Input {...register(`persons.${index}.first_name`)} />
          {errors[`person_${index}_first_name`] && (
            <p className="text-red-500 text-sm mt-1">{errors[`person_${index}_first_name`]}</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium mb-2">Soyisim</label>
          <Input {...register(`persons.${index}.last_name`)} />
          {errors[`person_${index}_last_name`] && (
            <p className="text-red-500 text-sm mt-1">{errors[`person_${index}_last_name`]}</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium mb-2">Uyruk</label>
          <Input {...register(`persons.${index}.nationality`)} defaultValue="Turkey" readOnly />
        </div>

        <div>
          <label className="block text-sm font-medium mb-2">Doğum Tarihi (GG/AA/YYYY)</label>
          <Input {...register(`persons.${index}.birth_date`)} placeholder="15/01/1990" />
          {errors[`person_${index}_birth_date`] && (
            <p className="text-red-500 text-sm mt-1">{errors[`person_${index}_birth_date`]}</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium mb-2">Pasaport No</label>
          <Input {...register(`persons.${index}.passport_number`)} placeholder="U12345678" />
          {errors[`person_${index}_passport_number`] && (
            <p className="text-red-500 text-sm mt-1">{errors[`person_${index}_passport_number`]}</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium mb-2">
            Geçerlilik Başlangıç (GG/AA/YYYY)
          </label>
          <Input {...register(`persons.${index}.passport_issue_date`)} placeholder="01/01/2020" />
          {errors[`person_${index}_passport_issue_date`] && (
            <p className="text-red-500 text-sm mt-1">
              {errors[`person_${index}_passport_issue_date`]}
            </p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium mb-2">
            Geçerlilik Bitiş (GG/AA/YYYY)
          </label>
          <Input {...register(`persons.${index}.passport_expiry_date`)} placeholder="01/01/2030" />
          {errors[`person_${index}_passport_expiry_date`] && (
            <p className="text-red-500 text-sm mt-1">
              {errors[`person_${index}_passport_expiry_date`]}
            </p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium mb-2">Telefon</label>
          <div className="flex gap-2">
            <Input
              {...register(`persons.${index}.phone_code`)}
              defaultValue="90"
              readOnly
              className="w-20"
            />
            <Input
              {...register(`persons.${index}.phone_number`)}
              placeholder="5551234567"
              className="flex-1"
            />
          </div>
          {errors[`person_${index}_phone_number`] && (
            <p className="text-red-500 text-sm mt-1">{errors[`person_${index}_phone_number`]}</p>
          )}
        </div>

        <div className="md:col-span-2">
          <label className="block text-sm font-medium mb-2">E-posta</label>
          <Input {...register(`persons.${index}.email`)} type="email" placeholder="ornek@email.com" />
          {errors[`person_${index}_email`] && (
            <p className="text-red-500 text-sm mt-1">{errors[`person_${index}_email`]}</p>
          )}
        </div>
      </div>
    </div>
  );
}

