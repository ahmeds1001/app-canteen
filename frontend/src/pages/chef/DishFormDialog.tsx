import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { dishApi } from "@/api/endpoints";
import { DISH_CATEGORIES, type Dish } from "@/api/types";
import { Alert, Button, Dialog, Field, SelectField, TextAreaField } from "@/components/ui";
import { useErrorMessage } from "@/hooks/useErrorMessage";

/** Create or edit a library dish (FR-29, FR-30). Also used from the planner to add a dish on the spot (FR-07). */
export function DishFormDialog({ dish, onClose, onSaved }: {
  dish?: Dish;
  onClose: () => void;
  onSaved?: (dish: Dish) => void;
}) {
  const { t } = useTranslation();
  const toMessage = useErrorMessage();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    name: dish?.name ?? "",
    category: dish?.category ?? "main",
    description: dish?.description ?? "",
    allergens: dish?.allergens ?? "",
  });
  const [photo, setPhoto] = useState<File | null>(null);
  const [error, setError] = useState("");

  const save = useMutation({
    mutationFn: () => (dish ? dishApi.update(dish.id, { ...form, photo }) : dishApi.create({ ...form, photo })),
    onSuccess: (saved) => {
      queryClient.invalidateQueries({ queryKey: ["dishes"] });
      onSaved?.(saved);
      onClose();
    },
    onError: (e) => setError(toMessage(e)),
  });

  const set = (key: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setError("");
    save.mutate();
  };

  return (
    <Dialog title={t(dish ? "dishes.edit" : "dishes.new")} onClose={onClose}>
      <form className="stack" onSubmit={submit}>
        {error && <Alert>{error}</Alert>}
        <Field label={t("dishes.name")} value={form.name} onChange={set("name")} required maxLength={120} autoFocus />
        <SelectField label={t("dishes.category")} value={form.category} onChange={set("category")}>
          {DISH_CATEGORIES.map((c) => (
            <option key={c} value={c}>{t(`dishes.categories.${c}`)}</option>
          ))}
        </SelectField>
        <TextAreaField label={t("dishes.description")} value={form.description} onChange={set("description")} />
        <Field
          label={t("dishes.allergens")}
          placeholder={t("dishes.allergensHint")}
          value={form.allergens}
          onChange={set("allergens")}
          maxLength={255}
        />
        <Field
          label={t("dishes.photo")}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          onChange={(e) => setPhoto(e.target.files?.[0] ?? null)}
        />
        <p className="muted dish-form__hint">{t("dishes.photoHint")}</p>
        <div className="actions">
          <Button type="submit" disabled={save.isPending}>{t("common.save")}</Button>
          <Button type="button" variant="ghost" onClick={onClose}>{t("common.cancel")}</Button>
        </div>
      </form>
    </Dialog>
  );
}
