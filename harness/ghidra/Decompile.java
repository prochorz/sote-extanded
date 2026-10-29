// Decompile the function that holds an address to pseudo-C (headless post-script for harness/decomp.py).
// Args: <addr hex> <out file>. If no function holds the address, disassemble there and create one from it.
// @category SotE
import java.io.PrintWriter;

import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;

public class Decompile extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String[] args = getScriptArgs();
        Address a = toAddr(Long.parseLong(args[0].replaceFirst("^0[xX]", ""), 16));
        String note = "";
        Function f = getFunctionContaining(a);
        if (f == null) {
            if (getInstructionAt(a) == null) {
                new DisassembleCommand(a, null, true).applyTo(currentProgram, monitor);
            }
            f = createFunction(a, null);
            note = " (created at the address: no function held it)";
        }
        try (PrintWriter w = new PrintWriter(args[1])) {
            if (f == null) {
                w.println("// no function could be made at " + a);
                return;
            }
            DecompInterface d = new DecompInterface();
            d.openProgram(currentProgram);
            DecompileResults r = d.decompileFunction(f, 60, monitor);
            w.println("// function " + f.getEntryPoint() + ", " + f.getBody().getNumAddresses() + " bytes" + note);
            if (r.decompileCompleted()) {
                w.print(r.getDecompiledFunction().getC());
            } else {
                w.println("// decompile failed: " + r.getErrorMessage());
            }
            d.dispose();
        }
    }
}
