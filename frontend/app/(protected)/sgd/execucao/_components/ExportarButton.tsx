"use client";

import { useState } from "react";
import { FileSpreadsheet, FileText } from "lucide-react";
import Spinner from "@/app/components/icons/Spinner";
import { Button } from "@/app/components/ui/Button/Button";
import {
  baixarExportacaoDemandas,
  type ExecucaoFiltros,
} from "@/app/lib/execucaoSgd";

export function ExportarButton({
  filtros,
}: {
  filtros: ExecucaoFiltros;
}) {
  const [exportando, setExportando] = useState<"csv" | "xlsx" | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const handleExport = async (formato: "csv" | "xlsx") => {
    try {
      setExportando(formato);
      setErro(null);
      await baixarExportacaoDemandas({ ...filtros, formato });
    } catch {
      setErro("Falha ao exportar arquivo. Tente novamente.");
    } finally {
      setExportando(null);
    }
  };

  return (
    <div className="flex flex-col items-end gap-1.5">
      <div className="flex items-center gap-2">
        <Button
          variant="secondary"
          size="sm"
          onClick={() => handleExport("csv")}
          disabled={exportando !== null}
          leftIcon={
            exportando === "csv" ? (
              <Spinner className="h-4 w-4" />
            ) : (
              <FileText className="h-4 w-4" />
            )
          }
          data-testid="exportar-csv-btn"
        >
          {exportando === "csv" ? "Exportando CSV..." : "Exportar CSV"}
        </Button>

        <Button
          variant="secondary"
          size="sm"
          onClick={() => handleExport("xlsx")}
          disabled={exportando !== null}
          leftIcon={
            exportando === "xlsx" ? (
              <Spinner className="h-4 w-4" />
            ) : (
              <FileSpreadsheet className="h-4 w-4" />
            )
          }
          data-testid="exportar-xlsx-btn"
        >
          {exportando === "xlsx" ? "Exportando Excel..." : "Exportar Excel"}
        </Button>
      </div>

      {erro && (
        <span className="text-2xs text-error-text" role="alert">
          {erro}
        </span>
      )}
    </div>
  );
}
