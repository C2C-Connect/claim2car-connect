/** Browser/Node VIN format and check-digit guard. Not a vehicle decoder or authenticity proof. */
export const VIN_WEIGHTS = Object.freeze([8,7,6,5,4,3,2,10,0,9,8,7,6,5,4,3,2]);
const VALUES = Object.freeze({A:1,B:2,C:3,D:4,E:5,F:6,G:7,H:8,J:1,K:2,L:3,M:4,N:5,P:7,R:9,S:2,T:3,U:4,V:5,W:6,X:7,Y:8,Z:9});
const MESSAGE = 'VIN VALIDATION FAILED: Recapture VIN Plate';
const SCOPE = 'format-and-check-digit-only';

export function validateVin(input) {
  const rawVin = typeof input === 'string' && input.length <= 256 ? input : null;
  let vin = null;
  const fail = (reason) => Object.freeze({ok:false,reason,message:MESSAGE,scope:SCOPE,rawVin,vin,
    normalizationChanged:rawVin !== null && vin !== null && rawVin !== vin,
    expectedCheckDigit:null,receivedCheckDigit:vin?.[8] ?? null});
  if (typeof input !== 'string') return fail('INVALID_INPUT');
  if (input.length > 256) return fail('INPUT_TOO_LONG');
  // Do not transliterate Unicode lookalikes or expand Unicode letters to ASCII.
  if (/[^\x00-\x7F]/.test(input)) return fail('ILLEGAL_CHARACTERS');
  vin = input.replace(/[^A-Za-z0-9]/g,'').toUpperCase();
  if (vin.length !== 17) return fail('INVALID_LENGTH');
  if (!/^[A-HJ-NPR-Z0-9]{17}$/.test(vin)) return fail('ILLEGAL_CHARACTERS');
  const sum = [...vin].reduce((total,char,index) => total +
    (char >= '0' && char <= '9' ? Number(char) : VALUES[char]) * VIN_WEIGHTS[index],0);
  const remainder = sum % 11;
  const expectedCheckDigit = remainder === 10 ? 'X' : String(remainder);
  const ok = vin[8] === expectedCheckDigit;
  return Object.freeze({ok,reason:ok ? null : 'CHECKSUM_MISMATCH',message:ok ? null : MESSAGE,
    scope:SCOPE,rawVin,vin,normalizationChanged:rawVin !== vin,
    expectedCheckDigit,receivedCheckDigit:vin[8]});
}
