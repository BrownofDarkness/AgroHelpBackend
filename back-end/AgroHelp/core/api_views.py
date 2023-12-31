from rest_framework.viewsets import GenericViewSet, ModelViewSet
from rest_framework.response import Response
from rest_framework.mixins import (
    CreateModelMixin,
    DestroyModelMixin,
    ListModelMixin,
    UpdateModelMixin,
    RetrieveModelMixin,
)
from rest_framework.decorators import action
from rest_framework.permissions import (
    IsAuthenticated,
    IsAdminUser,
)
from rest_framework.authentication import TokenAuthentication,SessionAuthentication
from django.contrib.auth import get_user_model
from rest_framework import status
from django.http import JsonResponse
from django.db.models import Count
import random

from rest_framework.viewsets import ViewSet

from .serializers import (
    AgriculturePracticeSerializer,
    SoilSerializer,
    SoilAreaSerializer,
    ParcelSerializer,
    CultureSerializer,
    SoilSerializerCreate,
    _CultureSerializer,
    SoilDetailSerializer,
    CultureDiseaseSerializer,
    FertilizerSerializer,
    CulturesIdsSerializer,
    RecommendedSerializer,
    SoilAreaSerializerCreate,
)

from .models import (
    Soil,
    SoilArea,
    Parcel,
    Culture,
    AgriculturePractice,
    CultureDiseaseAdvice,
    CultureParcel,
    Fertilizer,
)

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

User = get_user_model()


class SoilViewSet(ListModelMixin, RetrieveModelMixin, GenericViewSet):
    queryset = Soil.objects.all()
    authentication_classes = [TokenAuthentication,SessionAuthentication]

    def get_serializer_class(self, *args, **kwargs):
        if self.action in ["areas"]:
            return SoilAreaSerializer
        if self.action in ["list", "retrieve"]:
            return SoilDetailSerializer
        return SoilSerializer

    @action(methods=["GET"], detail=True)
    def areas(self, request, *args, **kwargs):
        """
        This action will get retrieve all the areas where that soil is been found
        """
        instance = self.get_object()
        soil_area = SoilArea.objects.filter(soil=instance)

        return Response(
            SoilAreaSerializer(soil_area, many=True, context={
                               "request": request}).data,
            status=200,
        )


class SoilAreaViewSet(
    CreateModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    DestroyModelMixin,
    ListModelMixin,
    GenericViewSet,
):
    def get_serializer_class(self):
        if self.request.method.upper() in ["POST", "PUT", "PATCH"]:
            return SoilAreaSerializerCreate

        return SoilAreaSerializer

    queryset = SoilArea.objects.all()


class ParcelViewSet(
    CreateModelMixin,
    DestroyModelMixin,
    ListModelMixin,
    UpdateModelMixin,
    RetrieveModelMixin,
    GenericViewSet,
):
    # serializer_class = ParcelSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [TokenAuthentication,SessionAuthentication]

    def get_serializer_class(self):
        if self.action in ["add_cultures","remove_cultures"]:
            return CulturesIdsSerializer

        return ParcelSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = Parcel.objects.filter(
            user=user.id
        )  # .distinct('cultures__culture__name')
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response(
            {"data": ParcelSerializer(instance).data, "success": True}, status=201
        )

    def update(self, request, *args, **kwargs):
        instance: Parcel = self.get_object()
        user = self.request.user
        if instance.user == user:
            return super().update(request, *args, **kwargs)
        return JsonResponse({"detail": "you are not allowed to update this parcel"})

    def delete(self, request, *args, **kwargs):
        instance: Parcel = self.get_object()
        user = self.request.user
        if instance.user == user:
            return super().delete(request, *args, **kwargs)
        return JsonResponse({"detail": "you are not allowed to delete this parcel"})

    @action(methods=["GET"], detail=True)
    def suggest_culture(self, request, *args, **kwargs):
        instance: Parcel = self.get_object()

        soils = Soil.objects.filter(
            areas__polygon__intersects=instance.location)
        cultures = Culture.objects.filter(soil_culture__soil__in=soils)
        sugg = _CultureSerializer(cultures, many=True, context={"request": request}).data
        results = []
        for culture in sugg:
            """
            Here i will check if a user practise this culture
            """
            favorite = Culture.objects.filter(
                parcel__culture__id=culture["id"], parcel__parcel =instance.id
            ).exists()
            data = {"culture": culture, "favorite": favorite}

            results.append(data)
        print(sugg)
        
        # return Response(SoilSerializer(soils, many=True).data)
        return Response(results)

    @action(methods=["POST"], detail=True)
    def add_cultures(self, request, *args, **kwargs):
        instance: Parcel = self.get_object()
        serializer = CulturesIdsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cultures = serializer.validated_data["ids"]

        if instance.user == request.user:
            for culture in cultures:
                try:
                    CultureParcel.objects.create(
                        culture=culture, parcel=instance)
                except:
                    pass
            return Response(
                {"message": f"Culture added successfully"},
                status=status.HTTP_201_CREATED,
            )
        return Response({"detail": "Not Allow"}, status=status.HTTP_403_FORBIDDEN)
    @action(methods=["POST"], detail=True)
    def remove_cultures(self,request, *args,**kwargs):
        instance: Parcel = self.get_object()
        serializer = CulturesIdsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cultures = serializer.validated_data["ids"]
        if instance.user == request.user:
            for culture in cultures:
                try:
                    cult = CultureParcel.objects.filter(culture = culture, parcel = instance)
                    cult.delete()
                except:
                    pass
            return Response(
                {"message": "Culture deleted succesfully"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"detail": "Not Allow"}, status=status.HTTP_403_FORBIDDEN)

    @action(methods=["GET"], detail=True)
    def get_soils(self, request, *args, **kwargs):
        instance: Parcel = self.get_object()
        soils = Soil.objects.filter(areas__polygon__intersects=instance.location)
        return Response(SoilSerializer(soils, many=True).data)


class CultureViewSet(
    DestroyModelMixin,
    ListModelMixin,
    UpdateModelMixin,
    RetrieveModelMixin,
    CreateModelMixin,
    GenericViewSet,
):
    authentication_classes = [TokenAuthentication,SessionAuthentication]
    
    def get_serializer_class(self):
        if self.action in ["list", "me", "retrieve"]:
            return CultureSerializer
        elif self.action in ["diseases"]:
            return CultureDiseaseSerializer
        elif self.action in ["practise"]:
            return AgriculturePracticeSerializer
        elif self.action in ["favorable_areas"]:
            return SoilAreaSerializer
        elif self.action in ["recommended"]:
            return RecommendedSerializer
        elif self.action in ["populars"]:
            return RecommendedSerializer
        else:
            return CultureSerializer

    # serializer_class = CultureSerializer

    def get_permissions(self):
        if self.request.method.upper() in ["POST", "PUT", "PATCH"]:
            permission_classes = [IsAdminUser]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        return Culture.objects.all()

    @action(methods=["get"], detail=False)
    def me(self, request):
        # From this `me` action i will gtet all the cultures that a user practise
        instance = Culture.objects.filter(
            parcel__parcel__user=self.request.user)
        # instance = self.get_object()
        return Response(CultureSerializer(instance, many=True).data)

    def update(self, request, *args, **kwargs):
        instance: Parcel = self.get_object()
        user = self.request.user
        if instance.user == user:
            return super().update(request, *args, **kwargs)
        return JsonResponse({"detail": "you are not allowed to update this culture"})

    def delete(self, request, *args, **kwargs):
        instance: Parcel = self.get_object()
        user = self.request.user
        if instance.user == user:
            return super().delete(request, *args, **kwargs)
        return JsonResponse({"detail": "you are not allowed to delete this culture"})

    @action(methods=["GET"], detail=True)
    def practise(self, request, *args, **kwargs):
        instance = self.get_object()
        practises = AgriculturePractice.objects.filter(culture=instance)

        return Response(AgriculturePracticeSerializer(practises, many=True).data)

    @action(methods=["GET"], detail=True)
    def diseases(self, request, *args, **kwargs):
        instance = self.get_object()
        practises = CultureDiseaseAdvice.objects.filter(culture=instance)

        return Response(CultureDiseaseSerializer(practises, many=True).data)

    @action(methods=["GET"], detail=True)
    def favorable_areas(self, request, *args, **kwargs):
        """
        This function will get the areas suitable for a crop to grow
        """
        instance = self.get_object()
        culture_areas = SoilArea.objects.filter(
            soil__soil_culture__culture=instance)
        return Response(SoilAreaSerializer(culture_areas, many=True).data)

    @action(methods=["GET"], detail=True)
    def fertilizers(self, request, *args, **kwargs):
        instance = self.get_object()
        fertislizers = Fertilizer.objects.filter(
            culture_fertilizer__culture=instance)
        return Response(FertilizerSerializer(fertislizers, many=True).data)

    @action(methods=["GET"], detail=False)
    def populars(self, request, *args, **kwargs):
        # popular_cultures = (
        #     Culture.objects.annotate(num_parcels=Count("parcel"))
        #     .select_related("parcel")
        #     .order_by("-num_parcels")
        # )

        parcels = Parcel.objects.filter(user=request.user.id)

        popular_cultures = (
            Culture.objects.annotate(culture_count=Count("parcel"))
            .filter(culture_count__gt=0)
            .order_by("-culture_count")
        )

        _popcultures = _CultureSerializer(
            popular_cultures, many=True, context={"request": request}
        ).data

        results = []

        for culture in _popcultures:
            """
            Here i will check if a user practise this culture
            """
            # favorite = Culture.objects.filter(
            #     Q(parcel__culture__id=culture["id"]) & Q(parcel__parcel__in=parcels)
            # ).exists()
            favorite = Culture.objects.filter(
                parcel__culture__id=culture["id"], parcel__parcel__in=parcels
            ).exists()
            data = {"culture": culture, "favorite": favorite}

            results.append(data)

        return Response(results)

    @action(methods=["GET"], detail=False)
    def recommended(self, request, *args, **kwargs):
        recomended_cultures = []
        parcels = Parcel.objects.filter(user=request.user.id)

        for parcel in parcels:
            soils = Soil.objects.filter(
                areas__polygon__intersects=parcel.location)
            cultures = Culture.objects.filter(soil_culture__soil__in=soils)
            _cultures = _CultureSerializer(
                cultures, many=True, context={"request": request}
            ).data
            for _c in _cultures:
                recomended_cultures.append(_c)

        """
        The function below simply remove the duplicates in the a list
        """
        seen = set()
        unique_recomended_cultures = [
            dict_
            for dict_ in recomended_cultures
            if not (dict_["id"] in seen or seen.add(dict_["id"]))
        ]
        """
        The output data will have the form
        ```json
        {
            culture:{
                ...
            },
            favorite:false
        }
        ```
        """

        results = []

        for culture in unique_recomended_cultures:
            """
            Here i will check if a user practise this culture
            """
            # favorite = Culture.objects.filter(
            #     Q(parcel__culture__id=culture["id"]) & Q(parcel__parcel__in=parcels)
            # ).exists()
            favorite = Culture.objects.filter(
                parcel__culture__id=culture["id"], parcel__parcel__in=parcels
            ).exists()
            data = {"culture": culture, "favorite": favorite}

            results.append(data)

        return Response(results)


culture_param = openapi.Parameter(
    "culture", openapi.IN_QUERY, description="culture name", type=openapi.TYPE_STRING
)
culture_response = openapi.Response(
    "response description", AgriculturePracticeSerializer
)


class CulturePractiseViewSet(
    DestroyModelMixin,
    ListModelMixin,
    UpdateModelMixin,
    RetrieveModelMixin,
    GenericViewSet,
):
    permission_classes = [IsAuthenticated]

    serializer_class = AgriculturePracticeSerializer
    authentication_classes = [TokenAuthentication,SessionAuthentication]


    def get_queryset(self):
        """Here i will get the agricultural practise for a given culture passed in the
        query parameter as culture"""
        culture = self.request.query_params.get("culture", None)
        if self.request.query_params.get("culture"):
            culture = Culture.objects.filter(name=culture)
        return AgriculturePractice.objects.all()

    @swagger_auto_schema(
        responses={200: AgriculturePracticeSerializer(many=True)},
        manual_parameters=culture_param,
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class FertilizerViewSet(ModelViewSet, GenericViewSet):
    permission_classes = [IsAuthenticated]

    queryset = Fertilizer.objects.all()

    serializer_class = FertilizerSerializer
    authentication_classes = [TokenAuthentication,SessionAuthentication]



fertilizer_param = openapi.Parameter(
    "fertilizer",
    openapi.IN_QUERY,
    description="fertilizer name",
    type=openapi.TYPE_STRING,
)

disease_param = openapi.Parameter(
    "disease", openapi.IN_QUERY, description="disease name", type=openapi.TYPE_STRING
)


class SearchViewSet(ViewSet):
    """
    This view help you search either culture , soil or fertilizer
    you just need to provide only one query parameter either ?soil=<soil_type> or ?culture=<culture_name> or ?fertilizer=<fertilizer_name>
    """

    permission_classes = [IsAuthenticated]
    authentication_classes = [TokenAuthentication,SessionAuthentication]


    @swagger_auto_schema(
        manual_parameters=[culture_param, fertilizer_param, disease_param]
    )
    def list(self, request, *args, **kwargs):
        culture = request.query_params.get("culture", None)

        disease = request.query_params.get("disease", None)

        fertilizer = request.query_params.get("fertilizer", None)

        if culture:
            cultures = Culture.objects.filter(name__icontains=culture)

            return Response(
                {
                    "results": _CultureSerializer(
                        cultures, many=True
                    ).data,
                }
            )

        if disease:
            diseases = CultureDiseaseAdvice.objects.filter(disease_name__icontains=disease)

            return Response(
                {
                    "results": CultureDiseaseSerializer(
                        diseases, many=True
                    ).data
                }
            )
        if fertilizer:
            fertilizers = Fertilizer.objects.filter(name__icontains=fertilizer)

            return Response(
                {
                    "results": FertilizerSerializer(
                        fertilizers, many=True
                    ).data
                }
            )

        if not disease or not culture or not fertilizer:
            return Response(
                {
                    "error": "Please provide query params either `soil`,`culture` ,or `fertilizer` "
                },
                status=404,
            )
