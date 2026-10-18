// ---------------------------------------------------------------------------
//  InstaladorVerdeID.exe - launcher do instalador do VerdeID
//
//  Recurso embutido: instalar.ps1  (gerado por compilar.ps1)
//
//  O executavel apenas localiza o PowerShell, extrai o script de instalacao
//  para um arquivo temporario e o executa passando a raiz do projeto.
//
//  Compatibilidade: C# 5 (.NET Framework 4.x, compilado pelo csc.exe nativo).
// ---------------------------------------------------------------------------

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text;
using System.Threading;

internal static class Instalador
{
    private const string RecursoScript = "Instalador.Script";
    private const string NomeScript = "instalar.ps1";
    private const string TituloJanela = "VerdeID - instalador de dependencias e inicializacao";

    private static string scriptTemporario;

    private static int Main(string[] args)
    {
        try
        {
            Console.OutputEncoding = Encoding.UTF8;
        }
        catch
        {
            // Alguns consoles não aceitam trocar a codificação. Ignorar.
        }

        try
        {
            Console.Title = TituloJanela;
        }
        catch
        {
        }

        string diretorioExe = AppDomain.CurrentDomain.BaseDirectory
            .TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);

        // O .exe mora na pasta "instalador", entao a raiz do projeto e a pasta acima.
        string raizProjeto = Path.GetFullPath(Path.Combine(diretorioExe, ".."));

        string caminhoScript = PrepararScript(diretorioExe);

        if (caminhoScript == null)
        {
            Falhar("Script de instalacao ('" + NomeScript + "') nao encontrado junto ao executavel.");
            return 1;
        }

        string powershell = LocalizarPowerShell();

        if (powershell == null)
        {
            Falhar("Windows PowerShell nao encontrado neste sistema.");
            return 1;
        }

        List<string> argumentos = new List<string>();
        argumentos.Add("-NoProfile");
        argumentos.Add("-ExecutionPolicy");
        argumentos.Add("Bypass");
        argumentos.Add("-File");
        argumentos.Add(Quote(caminhoScript));
        argumentos.Add("-Raiz");
        argumentos.Add(Quote(raizProjeto));

        for (int i = 0; i < args.Length; i++)
        {
            // "-Raiz" ja e informado acima. Repassar de novo quebraria o script,
            // pois o PowerShell nao aceita o mesmo parametro duas vezes.
            if (string.Equals(args[i], "-Raiz", StringComparison.OrdinalIgnoreCase))
            {
                i++;
                continue;
            }

            argumentos.Add(Quote(args[i]));
        }

        int codigo = Executar(powershell, string.Join(" ", argumentos.ToArray()));

        AguardarFechamento(args, codigo);

        return codigo;
    }

    // Usa o script embutido no executavel. Se nao houver recurso, cai para o
    // instalar.ps1 que estiver na mesma pasta do .exe.
    private static string PrepararScript(string diretorioExe)
    {
        Stream stream = null;

        try
        {
            stream = Assembly.GetExecutingAssembly()
                .GetManifestResourceStream(RecursoScript);
        }
        catch
        {
            stream = null;
        }

        if (stream != null)
        {
            try
            {
                string destino = Path.Combine(
                    Path.GetTempPath(),
                    "verdeid-instalar-" + Guid.NewGuid().ToString("N") + ".ps1"
                );

                using (StreamReader reader = new StreamReader(stream, Encoding.UTF8))
                {
                    string conteudo = reader.ReadToEnd();

                    // O BOM e necessario para o PowerShell 5.1 ler os acentos.
                    File.WriteAllText(destino, conteudo, new UTF8Encoding(true));
                }

                stream.Close();
                stream = null;

                scriptTemporario = destino;
                return destino;
            }
            catch (Exception erro)
            {
                Console.WriteLine("Aviso: nao foi possível extrair o script embutido (" + erro.Message + ").");

                if (stream != null)
                {
                    stream.Close();
                }
            }
        }

        string aoLado = Path.Combine(diretorioExe, NomeScript);

        return File.Exists(aoLado) ? aoLado : null;
    }

    private static string LocalizarPowerShell()
    {
        string[] candidatos = new string[]
        {
            Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.System),
                @"System32\WindowsPowerShell\v1.0\powershell.exe"),
            Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.System),
                @"SysWOW64\WindowsPowerShell\v1.0\powershell.exe"),
            "powershell.exe",
            "pwsh.exe"
        };

        for (int i = 0; i < candidatos.Length; i++)
        {
            string caminho = candidatos[i];

            if (string.IsNullOrEmpty(caminho))
            {
                continue;
            }

            if (caminho.IndexOf(Path.DirectorySeparatorChar) >= 0)
            {
                if (File.Exists(caminho))
                {
                    return caminho;
                }
            }
            else
            {
                string resolvido = BuscarNoPath(caminho);

                if (resolvido != null)
                {
                    return resolvido;
                }
            }
        }

        return null;
    }

    private static string BuscarNoPath(string executavel)
    {
        string caminho = Environment.GetEnvironmentVariable("PATH");

        if (string.IsNullOrEmpty(caminho))
        {
            return null;
        }

        string[] pastas = caminho.Split(
            new char[] { Path.PathSeparator },
            StringSplitOptions.RemoveEmptyEntries
        );

        for (int i = 0; i < pastas.Length; i++)
        {
            if (string.IsNullOrWhiteSpace(pastas[i]))
            {
                continue;
            }

            string completo = Path.Combine(pastas[i].Trim(), executavel);

            if (File.Exists(completo))
            {
                return completo;
            }
        }

        return null;
    }

    private static int Executar(string executavel, string argumentos)
    {
        ProcessStartInfo info = new ProcessStartInfo(executavel, argumentos);

        info.UseShellExecute = false;
        info.CreateNoWindow = false;
        info.WorkingDirectory = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);

        using (Process processo = new Process())
        {
            processo.StartInfo = info;

            try
            {
                processo.Start();
            }
            catch (Exception erro)
            {
                Falhar("Nao foi possivel executar o PowerShell: " + erro.Message);
                return 1;
            }

            processo.WaitForExit();

            return processo.ExitCode;
        }
    }

    // Mantem a janela aberta em execucao por duplo clique e sempre em caso de erro.
    private static void AguardarFechamento(string[] args, int codigo)
    {
        // Quando o executavel e iniciado por outro programa (script, tarefa,
        // terminal), a entrada padrao esta redirecionada e o ReadLine travaria
        // para sempre. Nesse caso nao ha janela para segurar o usuario.
        try
        {
            if (Console.IsInputRedirected)
            {
                return;
            }
        }
        catch
        {
        }

        bool manter = codigo != 0 || args.Length == 0;

        for (int i = 0; i < args.Length; i++)
        {
            if (string.Equals(args[i], "-ManterJanela", StringComparison.OrdinalIgnoreCase))
            {
                manter = true;
            }
        }

        if (!manter)
        {
            return;
        }

        Console.WriteLine();

        if (codigo != 0)
        {
            Console.WriteLine("A instalacao terminou com erro (codigo " + codigo + ").");
            Console.WriteLine("Consulte o arquivo instalar.log dentro da pasta instalador.");
            Console.WriteLine();
        }

        try
        {
            Console.WriteLine("Pressione ENTER para fechar esta janela...");
            Console.ReadLine();
        }
        catch
        {
        }
    }

    private static void Falhar(string mensagem)
    {
        Console.WriteLine();
        Console.WriteLine("ERRO: " + mensagem);
    }

    private static string Quote(string valor)
    {
        return "\"" + valor + "\"";
    }
}