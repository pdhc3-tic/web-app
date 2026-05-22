"use client";

import { useState } from "react";
import { Badge, BadgeStatus } from "../components/ui/Badge/Badge";
import { Button } from "../components/ui/Button/Button";
import { Input } from "../components/ui/Input/Input";
import { Select } from "../components/ui/Select/Select";
import { Textarea } from "../components/ui/Textarea/Textarea";

const BADGE_STATUSES: BadgeStatus[] = [
  "planejado",
  "agendado",
  "em-andamento",
  "concluido",
  "sem-evidencia",
  "adiada",
  "nao-realizada",
  "cancelada",
  "atrasada",
];

const TERRITORIOS = [
  { value: "bahia", label: "Bahia" },
  { value: "ceara", label: "Ceará" },
  { value: "paraiba", label: "Paraíba" },
  { value: "pernambuco", label: "Pernambuco" },
];

const MUNICIPIOS_MUITOS = [
  "Petrolina", "Juazeiro", "Salgueiro", "Serra Talhada", "Floresta",
  "Bom Jesus da Lapa", "Casa Nova", "Sento Sé", "Curaçá", "Sobradinho",
  "Senhor do Bonfim", "Jaguarari", "Uauá", "Andorinha", "Antas",
].map((m) => ({ value: m.toLowerCase().replace(/\s+/g, "-"), label: m }));

function Group({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-mono text-text-muted uppercase tracking-wide">{title}</p>
      <div className="flex flex-wrap gap-3 items-center bg-surface p-4 rounded-lg border border-border">
        {children}
      </div>
    </div>
  );
}

function ArrowRight() {
  return (
    <svg viewBox="0 0 16 16" width={14} height={14} fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 8h10M9 4l4 4-4 4" />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg viewBox="0 0 16 16" width={14} height={14} fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M8 3v10M3 8h10" />
    </svg>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-lg font-semibold text-text border-b border-border pb-2 mb-5">
      {children}
    </h2>
  );
}

export function ComponentsShowcase() {
  const [selectValue, setSelectValue] = useState<string>("");
  const [selectSearchValue, setSelectSearchValue] = useState<string>("");
  const [selectErrorValue, setSelectErrorValue] = useState<string>("");
  const [formNome, setFormNome] = useState("");
  const [formEmail, setFormEmail] = useState("");
  const [formObs, setFormObs] = useState("");
  const [formTerritorio, setFormTerritorio] = useState("");
  const [formSubmitted, setFormSubmitted] = useState(false);

  return (
    <>
      {/* ── 8 · Buttons ── */}
      <section>
        <SectionTitle>8 · Buttons</SectionTitle>
        <div className="space-y-6">
          <Group title="5 variantes (size md, default)">
            <Button variant="primary">Primary</Button>
            <Button variant="secondary">Secondary</Button>
            <Button variant="ghost">Ghost</Button>
            <Button variant="danger">Excluir</Button>
            <Button variant="icon-label" leftIcon={<PlusIcon />}>Adicionar</Button>
          </Group>

          <Group title="Tamanhos (primary)">
            <Button size="sm">Small</Button>
            <Button size="md">Medium</Button>
            <Button size="lg">Large</Button>
          </Group>

          <Group title="Estado loading (mostra spinner 14px + 'Salvando...')">
            <Button loading>Texto ignorado</Button>
            <Button variant="secondary" loading>Texto ignorado</Button>
            <Button variant="danger" loading>Texto ignorado</Button>
          </Group>

          <Group title="Estado disabled (opacity 40%, cursor not-allowed)">
            <Button disabled>Primary</Button>
            <Button variant="secondary" disabled>Secondary</Button>
            <Button variant="ghost" disabled>Ghost</Button>
            <Button variant="danger" disabled>Danger</Button>
          </Group>

          <Group title="leftIcon / rightIcon">
            <Button leftIcon={<PlusIcon />}>Novo</Button>
            <Button variant="secondary" rightIcon={<ArrowRight />}>Próximo</Button>
            <Button variant="ghost" leftIcon={<PlusIcon />} rightIcon={<ArrowRight />}>
              Ambos
            </Button>
          </Group>

          <Group title="as='a' (renderiza como link)">
            <Button as="a" href="#section-buttons" variant="primary">Link primário</Button>
            <Button as="a" href="#section-buttons" variant="secondary">Link secundário</Button>
          </Group>
        </div>
      </section>

      {/* ── 9 · Badges ── */}
      <section>
        <SectionTitle>9 · Badges (9 status semânticos)</SectionTitle>
        <Group title="Cada badge tem cor + ícone + label (regra de ouro: nunca só cor)">
          {BADGE_STATUSES.map((s) => (
            <Badge key={s} status={s} />
          ))}
        </Group>
      </section>

      {/* ── 10 · Inputs ── */}
      <section>
        <SectionTitle>10 · Inputs</SectionTitle>
        <div className="grid gap-5 sm:grid-cols-2">
          <Input label="Normal" placeholder="Digite aqui" />
          <Input
            label="Com helper text"
            placeholder="seu.email@dominio.com"
            helperText="Será usado para login e notificações."
          />
          <Input
            label="Required"
            placeholder="Nome completo"
            required
            helperText="Como aparece no documento oficial."
          />
          <Input
            label="Com erro"
            placeholder="CPF"
            defaultValue="111.111.111-1"
            error="CPF inválido. Confira os dígitos."
          />
          <Input
            label="Sucesso"
            defaultValue="adrian@email.com"
            success
            helperText="Email verificado."
          />
          <Input
            label="Disabled"
            defaultValue="Não editável"
            disabled
          />
        </div>
      </section>

      {/* ── 11 · Textarea ── */}
      <section>
        <SectionTitle>11 · Textarea</SectionTitle>
        <div className="grid gap-5 sm:grid-cols-2">
          <Textarea
            label="Observações"
            placeholder="Descreva o ocorrido..."
            helperText="Mínimo 30 caracteres."
          />
          <Textarea
            label="Obrigatório"
            placeholder="Justificativa"
            required
          />
          <Textarea
            label="Com erro"
            defaultValue="abc"
            error="Texto muito curto."
          />
          <Textarea
            label="Disabled"
            defaultValue="Conteúdo bloqueado."
            disabled
          />
        </div>
      </section>

      {/* ── 12 · Selects ── */}
      <section>
        <SectionTitle>12 · Select</SectionTitle>
        <div className="grid gap-5 sm:grid-cols-2">
          <Select
            label="Território (≤10 opções, sem busca)"
            options={TERRITORIOS}
            value={selectValue}
            onChange={setSelectValue}
            placeholder="Selecione um estado"
            helperText="Use as setas e Enter; Esc fecha."
          />
          <Select
            label="Município (>10 opções, com busca)"
            options={MUNICIPIOS_MUITOS}
            value={selectSearchValue}
            onChange={setSelectSearchValue}
            placeholder="Selecione o município"
            required
            helperText="Campo de busca aparece automaticamente."
          />
          <Select
            label="Com erro"
            options={TERRITORIOS}
            value={selectErrorValue}
            onChange={setSelectErrorValue}
            error="Selecione um território antes de continuar."
            placeholder="Obrigatório"
          />
          <Select
            label="Disabled"
            options={TERRITORIOS}
            value="bahia"
            disabled
          />
        </div>
      </section>

      {/* ── 13 · Form completo ── */}
      <section>
        <SectionTitle>13 · Formulário completo (Tab navega, Enter submete)</SectionTitle>
        <form
          className="bg-surface p-6 rounded-lg border border-border max-w-xl space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            setFormSubmitted(true);
          }}
        >
          <Input
            label="Nome"
            value={formNome}
            onChange={(e) => setFormNome(e.target.value)}
            required
            helperText="Nome completo conforme documento."
          />
          <Input
            label="E-mail"
            type="email"
            value={formEmail}
            onChange={(e) => setFormEmail(e.target.value)}
            required
          />
          <Select
            label="Território"
            options={TERRITORIOS}
            value={formTerritorio}
            onChange={setFormTerritorio}
            required
            placeholder="Selecione"
          />
          <Textarea
            label="Observações"
            value={formObs}
            onChange={(e) => setFormObs(e.target.value)}
            helperText="Opcional."
          />
          <div className="flex gap-3">
            <Button type="submit" variant="primary">Salvar</Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                setFormNome("");
                setFormEmail("");
                setFormObs("");
                setFormTerritorio("");
                setFormSubmitted(false);
              }}
            >
              Limpar
            </Button>
          </div>
          {formSubmitted && (
            <p className="text-xs text-success-text font-mono">
              ✓ Form submetido (apenas demo, nada foi enviado)
            </p>
          )}
        </form>
      </section>
    </>
  );
}
