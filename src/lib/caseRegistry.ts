import { Activity, Droplets, Waves, Trees, Building2, Pickaxe, ShieldAlert, Sprout } from "lucide-react";
import type { Phenomenon } from "../data/types";
export const caseIcons={earthquake:Activity,waterStress:Droplets,flood:Waves,deforestation:Trees,subsidence:Building2,miningExpansion:Pickaxe,tailingsInstability:ShieldAlert,miningRehabilitation:Sprout};
export const classColors:Record<Phenomenon,string>={earthquake:"#FF6B35",waterStress:"#F5B841",flood:"#3BA7FF",deforestation:"#3DDC84",subsidence:"#B57BFF",miningExpansion:"#FF4FA3",tailingsInstability:"#FF3B3B",miningRehabilitation:"#2DD4BF"};
