import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { 
  Code, 
  Play, 
  Download, 
  Share2, 
  FileText, 
  Image, 
  Music, 
  Settings,
  Eye,
  Copy,
  Check
} from "lucide-react";

const CodePreview = () => {
  const [activeTab, setActiveTab] = useState("preview");
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const files = [
    { name: "index.html", type: "file", icon: FileText, size: "2.4 KB" },
    { name: "style.css", type: "file", icon: FileText, size: "1.8 KB" },
    { name: "game.js", type: "file", icon: Code, size: "5.2 KB" },
    { name: "assets/", type: "folder", icon: Image, count: "3 files" },
    { name: "audio/", type: "folder", icon: Music, count: "2 files" },
  ];

  const sampleCode = `// Game Engine - Mamba Generated
class GamoraGame {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.width = canvas.width;
    this.height = canvas.height;
    
    this.player = {
      x: 50,
      y: this.height - 100,
      width: 40,
      height: 40,
      velocityY: 0,
      jumping: false,
      color: '#25D366'
    };
    
    this.platforms = [
      { x: 0, y: this.height - 20, width: this.width, height: 20 },
      { x: 200, y: this.height - 120, width: 150, height: 20 },
      { x: 400, y: this.height - 200, width: 150, height: 20 }
    ];
    
    this.init();
  }
  
  init() {
    this.gameLoop();
    this.bindEvents();
  }
  
  bindEvents() {
    document.addEventListener('keydown', (e) => {
      if (e.code === 'Space' && !this.player.jumping) {
        this.player.velocityY = -15;
        this.player.jumping = true;
      }
    });
  }
  
  update() {
    // Apply gravity
    this.player.velocityY += 0.8;
    this.player.y += this.player.velocityY;
    
    // Check platform collisions
    this.platforms.forEach(platform => {
      if (this.checkCollision(this.player, platform)) {
        this.player.y = platform.y - this.player.height;
        this.player.velocityY = 0;
        this.player.jumping = false;
      }
    });
  }
  
  render() {
    // Clear canvas
    this.ctx.clearRect(0, 0, this.width, this.height);
    
    // Draw platforms
    this.ctx.fillStyle = '#333';
    this.platforms.forEach(platform => {
      this.ctx.fillRect(platform.x, platform.y, platform.width, platform.height);
    });
    
    // Draw player
    this.ctx.fillStyle = this.player.color;
    this.ctx.fillRect(this.player.x, this.player.y, this.player.width, this.player.height);
  }
  
  checkCollision(rect1, rect2) {
    return rect1.x < rect2.x + rect2.width &&
           rect1.x + rect1.width > rect2.x &&
           rect1.y < rect2.y + rect2.height &&
           rect1.y + rect1.height > rect2.y;
  }
  
  gameLoop() {
    this.update();
    this.render();
    requestAnimationFrame(() => this.gameLoop());
  }
}

// Initialize game
const canvas = document.getElementById('gameCanvas');
const game = new GamoraGame(canvas);`;

  return (
    <div className="h-full flex flex-col bg-background-secondary/30">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border/50 bg-card/50">
        <div className="flex items-center space-x-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-primary">
            <Code className="h-4 w-4 text-white" />
          </div>
          <div>
            <h3 className="font-semibold">Platformer Game</h3>
            <p className="text-sm text-foreground-muted">Generated 2 minutes ago</p>
          </div>
        </div>
        
        <div className="flex items-center space-x-2">
          <Badge variant="secondary" className="bg-success/10 text-success border-success/20">
            <div className="h-2 w-2 bg-success rounded-full mr-2"></div>
            Ready
          </Badge>
          <Button variant="ghost" size="sm" onClick={handleCopy}>
            {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
          </Button>
          <Button variant="ghost" size="sm">
            <Share2 className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="sm">
            <Download className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col">
        <TabsList className="grid w-full grid-cols-3 bg-background-secondary/50 border-b border-border/50">
          <TabsTrigger value="preview" className="flex items-center space-x-2">
            <Eye className="h-4 w-4" />
            <span>Preview</span>
          </TabsTrigger>
          <TabsTrigger value="code" className="flex items-center space-x-2">
            <Code className="h-4 w-4" />
            <span>Code</span>
          </TabsTrigger>
          <TabsTrigger value="files" className="flex items-center space-x-2">
            <FileText className="h-4 w-4" />
            <span>Files</span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="preview" className="flex-1 p-0">
          <div className="h-full flex items-center justify-center bg-gradient-to-br from-background to-background-secondary">
            <Card className="w-[600px] h-[400px] overflow-hidden border-card-border shadow-lg">
              <div className="h-8 bg-muted flex items-center px-3 space-x-2">
                <div className="h-3 w-3 rounded-full bg-destructive"></div>
                <div className="h-3 w-3 rounded-full bg-warning"></div>
                <div className="h-3 w-3 rounded-full bg-success"></div>
                <span className="text-xs text-foreground-muted ml-2">Platformer Game</span>
              </div>
              <div className="h-[calc(100%-2rem)] bg-gradient-to-b from-blue-400 to-blue-600 relative overflow-hidden">
                {/* Game Preview */}
                <div className="absolute bottom-0 left-0 w-full h-5 bg-gray-800"></div>
                <div className="absolute bottom-5 left-[200px] w-[150px] h-5 bg-gray-700"></div>
                <div className="absolute bottom-5 left-[400px] w-[150px] h-5 bg-gray-700"></div>
                <div className="absolute bottom-5 left-[50px] w-10 h-10 bg-gamora-green rounded animate-bounce"></div>
                
                <div className="absolute top-4 left-4 bg-black/50 text-white px-3 py-2 rounded-lg text-sm">
                  <div className="flex items-center space-x-2">
                    <Play className="h-4 w-4" />
                    <span>Press SPACE to jump</span>
                  </div>
                </div>
              </div>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="code" className="flex-1 p-0">
          <div className="h-full overflow-hidden">
            <pre className="h-full overflow-auto custom-scrollbar p-6 text-sm font-mono bg-muted/30">
              <code className="text-foreground">{sampleCode}</code>
            </pre>
          </div>
        </TabsContent>

        <TabsContent value="files" className="flex-1 p-6">
          <div className="space-y-2">
            {files.map((file, index) => (
              <div
                key={index}
                className="flex items-center justify-between p-3 rounded-lg border border-card-border hover:bg-muted/30 transition-colors cursor-pointer"
              >
                <div className="flex items-center space-x-3">
                  <file.icon className="h-5 w-5 text-foreground-muted" />
                  <div>
                    <p className="font-medium">{file.name}</p>
                    <p className="text-sm text-foreground-muted">
                      {file.type === 'file' ? file.size : file.count}
                    </p>
                  </div>
                </div>
                <Button variant="ghost" size="sm">
                  <Download className="h-4 w-4" />
                </Button>
              </div>
            ))}
          </div>
        </TabsContent>
      </Tabs>

      {/* Actions */}
      <div className="border-t border-border/50 p-4 bg-card/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Button variant="default" className="bg-gradient-primary hover:opacity-90">
              <Play className="h-4 w-4 mr-2" />
              Run Game
            </Button>
            <Button variant="outline">
              <Settings className="h-4 w-4 mr-2" />
              Configure
            </Button>
          </div>
          
          <div className="flex items-center space-x-2 text-sm text-foreground-muted">
            <span>5 files generated</span>
            <span>•</span>
            <span>15.2 KB total</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CodePreview;