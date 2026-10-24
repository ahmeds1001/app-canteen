import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { dishApi } from "@/api/endpoints";
import { DISH_CATEGORIES, type Dish } from "@/api/types";
import { Alert, Badge, Button, Card, Field, SelectField } from "@/components/ui";
import { useErrorMessage } from "@/hooks/useErrorMessage";
import { formatShortDate } from "@/utils/dates";
import { DishFormDialog } from "./DishFormDialog";
import "./chef.css";

/** FR-29 to FR-31: the chef's dish library with search, category filter and last served date. */
export default function DishesPage() {
  const { t, i18n } = useTranslation();
  const toMessage = useErrorMessage();
  const queryClient = useQueryClient();
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const [archived, setArchived] = useState(false);
  const [editing, setEditing] = useState<Dish | "new" | null>(null);
  const [error, setError] = useState("");

  const dishes = useQuery({
    queryKey: ["dishes", { q, category, archived }],
    queryFn: () => dishApi.list({ q, category, archived }),
    placeholderData: keepPreviousData,
  });
  const archive = useMutation({
    mutationFn: dishApi.archive,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["dishes"] }),
    onError: (e) => setError(toMessage(e)),
  });

  return (
    <div className="container stack">
      <div className="page-head">
        <h1>{t("dishes.title")}</h1>
        <Button onClick={() => setEditing("new")}>{t("dishes.new")}</Button>
      </div>
      <div className="toolbar">
        <Field label={t("common.search")} type="search" value={q} onChange={(e) => setQ(e.target.value)} />
        <SelectField label={t("dishes.category")} value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">{t("dishes.allCategories")}</option>
          {DISH_CATEGORIES.map((c) => (
            <option key={c} value={c}>{t(`dishes.categories.${c}`)}</option>
          ))}
        </SelectField>
        <label className="check">
          <input type="checkbox" checked={archived} onChange={(e) => setArchived(e.target.checked)} />
          {t("dishes.showArchived")}
        </label>
      </div>
      {error && <Alert>{error}</Alert>}
      {dishes.data?.length === 0 && <p className="muted">{t("dishes.empty")}</p>}
      <div className="dish-grid">
        {dishes.data?.map((dish) => (
          <Card key={dish.id} className="dish">
            {dish.photo && <img className="dish__photo" src={dish.photo} alt="" loading="lazy" />}
            <div className="dish__head">
              <h3>{dish.name}</h3>
              <Badge>{t(`dishes.categories.${dish.category}`)}</Badge>
            </div>
            {dish.description && <p className="dish__desc">{dish.description}</p>}
            {dish.allergens && (
              <p className="dish__meta">{t("dishes.allergensLabel", { list: dish.allergens })}</p>
            )}
            <p className="dish__meta">
              {dish.last_served_on
                ? t("dishes.lastServed", { date: formatShortDate(dish.last_served_on, i18n.language) })
                : t("dishes.neverServed")}
            </p>
            {dish.is_archived ? (
              <Badge tone="orange">{t("dishes.archived")}</Badge>
            ) : (
              <div className="actions dish__actions">
                <Button className="btn--sm" variant="ghost" onClick={() => setEditing(dish)}>
                  {t("common.edit")}
                </Button>
                <Button
                  className="btn--sm"
                  variant="danger"
                  disabled={archive.isPending}
                  onClick={() => window.confirm(t("dishes.archiveConfirm", { name: dish.name })) && archive.mutate(dish.id)}
                >
                  {t("dishes.archive")}
                </Button>
              </div>
            )}
          </Card>
        ))}
      </div>
      {editing && (
        <DishFormDialog dish={editing === "new" ? undefined : editing} onClose={() => setEditing(null)} />
      )}
    </div>
  );
}
