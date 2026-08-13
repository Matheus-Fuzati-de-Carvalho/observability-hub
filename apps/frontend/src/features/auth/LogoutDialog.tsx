import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

interface LogoutDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: () => void
  isLoggingOut: boolean
}

export function LogoutDialog({ open, onOpenChange, onConfirm, isLoggingOut }: LogoutDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Sair da conta</DialogTitle>
          <DialogDescription>Deseja encerrar sua sessão?</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button disabled={isLoggingOut} onClick={onConfirm}>
            Sair
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
