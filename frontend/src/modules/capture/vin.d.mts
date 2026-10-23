export type VinFailure = 'INVALID_INPUT' | 'INPUT_TOO_LONG' | 'INVALID_LENGTH' | 'ILLEGAL_CHARACTERS' | 'CHECKSUM_MISMATCH';
interface VinBase {
  readonly scope: 'format-and-check-digit-only';
  readonly rawVin: string | null;
  readonly vin: string | null;
  readonly normalizationChanged: boolean;
  readonly expectedCheckDigit: string | null;
  readonly receivedCheckDigit: string | null;
}
export interface VinValid extends VinBase {
  readonly ok: true;
  readonly reason: null;
  readonly message: null;
  readonly rawVin: string;
  readonly vin: string;
  readonly expectedCheckDigit: string;
  readonly receivedCheckDigit: string;
}
export interface VinInvalid extends VinBase {
  readonly ok: false;
  readonly reason: VinFailure;
  readonly message: 'VIN VALIDATION FAILED: Recapture VIN Plate';
}
export type VinValidation = VinValid | VinInvalid;
export const VIN_WEIGHTS: readonly number[];
export function validateVin(input: unknown): VinValidation;
