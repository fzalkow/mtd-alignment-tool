/* jshint esversion: 6 */

var canvas;
var image_scale_factor;
var wav_circles = [];
var mid_circles = [];
var chroma = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'].reverse();

function convert_coord(x) {
  return x * image_scale_factor * matrix_scale_factor;
}

function unconvert_coord(x) {
  return x / (image_scale_factor * matrix_scale_factor);
}

function makeCircle(left_center, top_center, line1, line2, i) {
  var radius = 6;
  var stroke = 2;

  var c = new fabric.Circle({
    left: convert_coord(left_center),
    top: convert_coord(top_center),
    strokeWidth: stroke,
    radius: radius,
    fill: "red",
    stroke: "yellow",
    originX: "center",
    originY: "center"
  });
  c.hasControls = c.hasBorders = false;

  c.line1 = line1;
  c.line2 = line2;
  c.i = i;

  return c;
}

function makeLine(x1, y1, x2, y2) {
  return new fabric.Line(
    [convert_coord(x1), convert_coord(y1), convert_coord(x2), convert_coord(y2)], {
      fill: "red",
      stroke: "red",
      strokeWidth: 1,
      selectable: false,
      evented: false,
      originX: "center",
      originY: "center"
    });
}

function create_warping_path(wp) {
  var c, l_wav, l_mid, l_align;

  for (var i = 0; i < wp.length; i++) {

    l_mid = makeLine(wp[i][0], 12 * 2.5, wp[i][0], 12 * 1.5);
    canvas.add(l_mid);

    l_align = makeLine(wp[i][0], 12 * 1.5, wp[i][1], 12);
    canvas.add(l_align);

    l_wav = makeLine(wp[i][1], 12, wp[i][1], 0);
    canvas.add(l_wav);

    c = makeCircle(wp[i][0], 12 * 1.5, l_mid, l_align, i);
    c.set({
      selectable: false
    });
    canvas.add(c);
    mid_circles.push(c);

    c = makeCircle(wp[i][1], 12, l_wav, l_align, i);
    canvas.add(c);
    wav_circles.push(c);

  }
}

$(document).ready(function() {
  canvas = new fabric.Canvas("picCanv");
  canvas.selection = false;

  canvas_height = $("#canvasContainer").height();
  canvas_width = $("#canvasContainer").width();

  var img_tag_wav = document.getElementById("picImg_wav");
  var img_tag_mid = document.getElementById("picImg_mid");
  var img_wav = new fabric.Image(img_tag_wav);
  var img_mid = new fabric.Image(img_tag_mid);

  image_scale_factor = canvas_width / Math.max(img_tag_wav.naturalWidth, img_tag_mid.naturalWidth);

  canvas.setWidth(canvas_width);
  canvas.setHeight((img_tag_wav.naturalHeight * 1.5 + img_tag_mid.naturalHeight) * image_scale_factor);

  fabric.Image.fromURL(img_tag_wav.src, function(myImg) {
    img_wav.set({
      top: 0,
      scaleX: image_scale_factor,
      scaleY: image_scale_factor,
      originX: "left",
      originY: "top",
      selectable: false,
      strokeWidth: 3,
      stroke: 'black'
    });

    fabric.Image.fromURL(img_tag_mid.src, function(myImg) {
      img_mid.set({
        top: (img_tag_wav.naturalHeight * 1.5) * image_scale_factor,
        scaleX: image_scale_factor,
        scaleY: image_scale_factor,
        originX: "left",
        originY: "top",
        selectable: false,
        strokeWidth: 3,
        stroke: 'black'
      });

      canvas.add(img_wav);
      canvas.add(img_mid);
      create_warping_path(wp);

      for (var i = 0; i < Math.ceil(img_tag_wav.naturalWidth / (image_scale_factor * matrix_scale_factor)); i++) {
        l = new fabric.Line(
          [convert_coord(i), convert_coord(0), convert_coord(i), convert_coord(12)], {
            fill: "black",
            stroke: "black",
            strokeWidth: 1,
            selectable: false,
            evented: false,
            originX: "center",
            originY: "center",
            opacity: 0.2
          });
        canvas.add(l);
      }

      for (i = 0; i < Math.ceil(img_tag_mid.naturalWidth / (image_scale_factor * matrix_scale_factor)); i++) {
        l = new fabric.Line(
          [convert_coord(i), convert_coord(18), convert_coord(i), convert_coord(18 + 12)], {
            fill: "black",
            stroke: "black",
            strokeWidth: 1,
            selectable: false,
            evented: false,
            originX: "center",
            originY: "center",
            opacity: 0.2
          });
        canvas.add(l);
      }

    });
  });

  canvas.on("object:moving", function(e) {
    var target = e.target;
    var transform = e.transform;
    var top = transform.original.top;
    var left = target.left;
    var idx = target.i;

    if (idx == 0) {
      left = Math.min(left, wav_circles[idx + 1].left);
    } else if (idx == (wav_circles.length - 1)) {
      left = Math.max(left, wav_circles[idx - 1].left);
    } else {
      left = Math.max(left, wav_circles[idx - 1].left);
      left = Math.min(left, wav_circles[idx + 1].left);
    }

    // don't let circles go out of canvas
    left = Math.max(left, 0);
    left = Math.min(left, canvas.width);

    target.set({
      "top": top,
      "left": left
    });
    target.line1.set({
      "x1": left,
      "x2": left
    });
    target.line2.set({
      "x2": left
    });

    canvas.renderAll();
  });

  canvas.on('mouse:move', function(e) {
    var x = unconvert_coord(e.absolutePointer.x);
    var y = unconvert_coord(e.absolutePointer.y);

    if ((y >= 0) && (y < 12)) {
      document.getElementById("legend_modality").textContent = "WAV";
      document.getElementById("legend_chroma").textContent = chroma[Math.floor(y)];
      document.getElementById("legend_time").textContent = (x / feature_rate).toFixed(1);

    } else if ((y >= 12 * 1.5) && (y < 12 * 2.5)) {
      document.getElementById("legend_modality").textContent = "MID";
      document.getElementById("legend_chroma").textContent = chroma[Math.floor(y - (1.5 * 12))];
      document.getElementById("legend_time").textContent = (x / feature_rate).toFixed(1);
    } else {
      document.getElementById("legend_modality").textContent = "";
      document.getElementById("legend_chroma").textContent = "";
      document.getElementById("legend_time").textContent = "";
    }
  });

  canvas.on('mouse:out', function(e) {
    document.getElementById("legend_modality").textContent = "";
    document.getElementById("legend_chroma").textContent = "";
    document.getElementById("legend_time").textContent = "";
  });

  $("input#StartTime").trigger("input");
  $("input#EndTime").trigger("input");

});

$("#form_alignment, #form_save").submit(function() {

  var wp = new Array(wav_circles.length);
  for (var i = 0; i < wav_circles.length; i++) {
    wp[i] = [unconvert_coord(mid_circles[i].left), unconvert_coord(wav_circles[i].left)];
  }
  $(this).children("input[name='alignment']").val(JSON.stringify(wp));

  return true;
});

$("input#StartTime").on("input", function() {
  var val = parseFloat($("input#StartTime").val()) + 0.1;
  val = (Math.round(val * 10) / 10).toFixed(1);
  $("input#EndTime").attr("min", val);
});

$("input#EndTime").on("input", function() {
  var val = parseFloat($("input#EndTime").val()) - 0.1;
  val = (Math.round(val * 10) / 10).toFixed(1);
  $("input#StartTime").attr("max", val);
});
