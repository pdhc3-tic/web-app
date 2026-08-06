import { notFound } from "next/navigation";
import Link from "next/link";
import { ChevronLeftIcon } from "../../components/icons";
import { MapsShowcase } from "./MapsShowcase";

export default function StyleguideMapsPage() {
  if (process.env.NODE_ENV === "production") {
    notFound();
  }

  return (
    <div className="min-h-screen bg-bg">
      <div className="max-w-5xl mx-auto px-6 py-10 space-y-10">
        <header>
          <div className="flex items-center justify-between mb-3">
            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-warning-bg text-warning-text text-micro font-medium uppercase tracking-wide border border-border">
              Dev only · NODE_ENV = {process.env.NODE_ENV}
            </span>
            <Link
              href="/styleguide"
              className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md border border-border bg-surface text-sm font-medium text-text hover:bg-surface-muted transition-colors"
            >
              <ChevronLeftIcon className="h-3.5 w-3.5" />
              Guia de Estilo
            </Link>
          </div>
          <h1 className="text-4xl font-bold tracking-tight text-text">
            MapView · Mapa reusável
          </h1>
          <p className="mt-2 text-sm text-text-muted">
            Leaflet + OpenStreetMap. Markers por status, clustering automático e
            popups no design system.<br />
            Esta página retorna 404 em produção.
          </p>
        </header>

        <MapsShowcase />
      </div>
    </div>
  );
}
