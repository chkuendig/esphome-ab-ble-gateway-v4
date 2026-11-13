// Locate Xtensa tick timer setup in the installed ESP32 image, read-only.
// @category AprilBrother
import java.nio.file.*;
import java.util.*;
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;

public class FindTickSetup extends GhidraScript {
  public void run() throws Exception {
    Path out=Paths.get(getScriptArgs()[0]); Files.createDirectories(out);
    LinkedHashSet<Function> functions=new LinkedHashSet<>();
    StringBuilder hits=new StringBuilder();
    InstructionIterator it=currentProgram.getListing().getInstructions(true);
    while(it.hasNext()) {
      Instruction ins=it.next(); String s=ins.toString().toLowerCase();
      if(s.contains("ccompare")) {
        Function f=getFunctionContaining(ins.getAddress());
        hits.append(ins.getAddress()).append(" ").append(s).append(" function=")
          .append(f==null?"none":f.getEntryPoint()).append("\n");
        if(f!=null)functions.add(f);
      }
    }
    DecompInterface dc=new DecompInterface();dc.openProgram(currentProgram);
    for(Function f:functions) {
      DecompileResults r=dc.decompileFunction(f,30,monitor);
      Files.writeString(out.resolve(f.getEntryPoint()+".c"),r.decompileCompleted()?r.getDecompiledFunction().getC():r.getErrorMessage());
      StringBuilder asm=new StringBuilder();it=currentProgram.getListing().getInstructions(f.getBody(),true);
      while(it.hasNext()){Instruction ins=it.next();asm.append(ins.getAddress()).append(" ").append(ins).append("\n");}
      Files.writeString(out.resolve(f.getEntryPoint()+".asm"),asm.toString());
    }
    dc.dispose();Files.writeString(out.resolve("tick-hits.txt"),hits.toString());println(hits.toString());
  }
}
