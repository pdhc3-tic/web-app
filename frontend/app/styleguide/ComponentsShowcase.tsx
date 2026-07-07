"use client";

import { Fragment, useState } from "react";
import { Badge, BadgeStatus } from "../components/ui/Badge/Badge";
import { Button } from "../components/ui/Button/Button";
import { Input } from "../components/ui/Input/Input";
import { Select } from "../components/ui/Select/Select";
import { Textarea } from "../components/ui/Textarea/Textarea";
import { ArrowRightIcon, DocumentIcon, PlusIcon } from "../components/icons";
import { Search, Mail } from "lucide-react";
import { SlideOver } from "../components/ui/SlideOver/SlideOver";

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

  // ── Estados para demos do SlideOver ────────────────────────────────────────
  const [openView, setOpenView] = useState(false);
  const [openEdit, setOpenEdit] = useState(false);
  const [openTabs, setOpenTabs] = useState(false);
  const [activeTab, setActiveTab] = useState(0);
  const [editDesc, setEditDesc] = useState("Mobilização comunitária no semiárido");
  const [editTerr, setEditTerr] = useState("bahia");

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
            <Button variant="secondary" rightIcon={<ArrowRightIcon />}>Próximo</Button>
            <Button variant="ghost" leftIcon={<PlusIcon />} rightIcon={<ArrowRightIcon />}>
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
          <Input
            label="Com ícone à esquerda"
            placeholder="Buscar por nome ou e-mail..."
            startIcon={<Search className="h-4 w-4" />}
          />
          <Input
            label="Com ícone à esquerda"
            type="email"
            placeholder="seu.email@dominio.com"
            startIcon={<Mail className="h-4 w-4" />}
            helperText="Ícone combina com o tipo do campo."
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

      {/* ── 14 · SlideOver ── */}
      <section>
        <SectionTitle>14 · SlideOver — Painel de Detalhe</SectionTitle>
        <p className="text-sm text-text-muted mb-5">
          Componente base reutilizável para todos os módulos. Anima da direita (250 ms
          ease-out). Esc fecha e devolve foco à origem.{" "}
          <code className="font-mono text-xs bg-surface-muted px-1 py-0.5 rounded">aria-modal=&quot;false&quot;</code>
          {" "}— não bloqueia foco (padrão inline).
        </p>
        <div className="flex flex-wrap gap-3">
          <Button variant="secondary" onClick={() => setOpenView(true)}>
            Visualização (leitura)
          </Button>
          <Button variant="secondary" onClick={() => setOpenEdit(true)}>
            Edição (formulário + rodapé)
          </Button>
          <Button
            variant="secondary"
            onClick={() => { setActiveTab(0); setOpenTabs(true); }}
          >
            Com abas internas
          </Button>
        </div>

        {/* Demo 1: Modo visualização */}
        <SlideOver
          open={openView}
          onClose={() => setOpenView(false)}
          title="Família Pereira — UPF #042"
          badge={<Badge status="em-andamento" />}
          breadcrumb="SGP / Unidades Produtivas / #042"
          actions={
            <Button
              variant="secondary"
              size="sm"
              onClick={() => { setOpenView(false); setOpenEdit(true); }}
            >
              Editar
            </Button>
          }
        >
          <div className="p-5 space-y-5">
            <dl className="grid grid-cols-[auto_1fr] items-baseline gap-x-6 gap-y-3 text-sm">
              {([
                ["Responsável", "João Pereira"],
                ["Município", "Petrolina – PE"],
                ["Território", "Vale do São Francisco"],
                ["Área total", "3,2 ha"],
                ["Atividade principal", "Apicultura"],
                ["Data de cadastro", "12 mar 2026"],
                ["Status", "Em acompanhamento ativo"],
              ] as [string, string][]).map(([label, value]) => (
                <Fragment key={label}>
                  <dt className="text-text-muted whitespace-nowrap">{label}</dt>
                  <dd className="text-text font-medium">{value}</dd>
                </Fragment>
              ))}
            </dl>
            <div className="rounded-md bg-surface-muted border border-border p-4 text-sm text-text-muted leading-relaxed">
              <p className="font-medium text-text mb-1">Observações</p>
              Família cadastrada no PRONAF. Prioridade alta para visita técnica no
              próximo ciclo. Última visita realizada em fevereiro de 2026.
            </div>
          </div>
        </SlideOver>

        {/* Demo 2: Modo edição (formulário + rodapé) */}
        <SlideOver
          open={openEdit}
          onClose={() => setOpenEdit(false)}
          title="Editar Atividade — #015"
          badge={<Badge status="agendado" />}
          breadcrumb="SGE / Atividades / #015"
          width="wide"
          footer={
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setOpenEdit(false)}>Cancelar</Button>
              <Button variant="primary" onClick={() => setOpenEdit(false)}>Salvar alterações</Button>
            </div>
          }
        >
          <div className="p-5 space-y-4">
            <Input
              label="Descrição"
              value={editDesc}
              onChange={(e) => setEditDesc(e.target.value)}
              required
            />
            <Select
              label="Território"
              options={TERRITORIOS}
              value={editTerr}
              onChange={setEditTerr}
              required
              placeholder="Selecione"
            />
            <div className="grid grid-cols-2 gap-4">
              <Input label="Data de início" type="date" defaultValue="2026-06-10" />
              <Input label="Data de término" type="date" defaultValue="2026-06-12" />
            </div>
            <Textarea
              label="Observações"
              placeholder="Informações complementares..."
              helperText="Opcional."
            />
          </div>
        </SlideOver>

        {/* Demo 3: Com abas internas */}
        <SlideOver
          open={openTabs}
          onClose={() => setOpenTabs(false)}
          title="Demanda #128 — Regularização fundiária"
          badge={<Badge status="em-andamento" />}
          breadcrumb="SGD / Demandas / #128"
          actions={<Button variant="secondary" size="sm">Editar</Button>}
          tabs={
            <div className="flex px-2">
              {(["Detalhes", "Histórico", "Documentos"] as const).map((tab, i) => (
                <button
                  key={tab}
                  type="button"
                  onClick={() => setActiveTab(i)}
                  className={[
                    "px-4 py-3 text-sm font-medium border-b-2 -mb-px transition-colors duration-120",
                    activeTab === i
                      ? "border-primary text-primary"
                      : "border-transparent text-text-muted hover:text-text hover:border-border",
                  ].join(" ")}
                >
                  {tab}
                </button>
              ))}
            </div>
          }
        >
          {activeTab === 0 && (
            <div className="p-5">
              <dl className="grid grid-cols-[auto_1fr] items-baseline gap-x-6 gap-y-3 text-sm">
                {([
                  ["Beneficiário", "Maria da Conceição Silva"],
                  ["Tipo", "Regularização fundiária"],
                  ["Território", "Sertão do São Francisco"],
                  ["Prioridade", "Alta"],
                  ["Abertura", "02 mai 2026"],
                  ["Responsável técnico", "Ana Paula Ramos"],
                ] as [string, string][]).map(([label, value]) => (
                  <Fragment key={label}>
                    <dt className="text-text-muted whitespace-nowrap">{label}</dt>
                    <dd className="text-text font-medium">{value}</dd>
                  </Fragment>
                ))}
              </dl>
            </div>
          )}
          {activeTab === 1 && (
            <ul className="divide-y divide-border">
              {[
                { data: "20 mai 2026", texto: "Demanda encaminhada para análise jurídica." },
                { data: "15 mai 2026", texto: "Documentação complementar recebida pela equipe." },
                { data: "07 mai 2026", texto: "Vistoria de campo realizada sem pendências." },
                { data: "02 mai 2026", texto: "Demanda registrada no sistema pelo técnico responsável." },
              ].map((item) => (
                <li key={item.data} className="flex gap-4 px-5 py-3 text-sm">
                  <span className="text-text-muted whitespace-nowrap tabular-nums">{item.data}</span>
                  <span className="text-text">{item.texto}</span>
                </li>
              ))}
            </ul>
          )}
          {activeTab === 2 && (
            <div className="flex flex-col items-center justify-center gap-3 py-16 text-text-muted">
              <DocumentIcon className="h-10 w-10 opacity-40" />
              <p className="text-sm">Nenhum documento anexado.</p>
            </div>
          )}
        </SlideOver>
      </section>
    </>
  );
}
