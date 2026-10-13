import { useState } from "react";
import { Modal } from "@/components/ui";
import FichaPadronAdministrativa from "./FichaPadronAdministrativa";

// Los recursos conservan sus guardados independientes dentro de un solo diálogo.
export default function EditarFichaPadron({ onClose, ...props }) {
  const [ocupado, setOcupado] = useState(false);
  return <Modal title="Editar ficha administrativa" ayuda="Cada bloque se guarda con su motivo. Las fechas administrativas no finalizan derechos; la cobertura se administra con las acciones explícitas del padrón." width={960} onClose={ocupado ? undefined : onClose}>
    <FichaPadronAdministrativa {...props} integrado onOcupado={setOcupado} />
  </Modal>;
}
